"""E2E tests for the debug breakpoint stack.

Composition under test (same as production):

    UiPathDebugRuntime              ← bridge I/O, resume loop
      └─ UiPathDebugFunctionsRuntime ← sys.settrace line breakpoints
           └─ UiPathFunctionsRuntime  ← loads & executes user code

MockDebugBridge implements UiPathDebugProtocol (same interface as
ConsoleDebugBridge / SignalRDebugBridge) and auto-resumes on every
breakpoint so the full loop completes without human interaction.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Any, Literal, cast

import pytest

from uipath.functions.debug import (
    BreakpointController,
    UiPathDebugFunctionsRuntime,
    _is_debugger_tracer,
    _new_stop_once_task,
)
from uipath.functions.runtime import UiPathFunctionsRuntime
from uipath.runtime import (
    UiPathBreakpointResult,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.debug import UiPathDebugRuntime
from uipath.runtime.events import UiPathRuntimeStateEvent, UiPathRuntimeStatePhase


class MockDebugBridge:
    """Test double that implements UiPathDebugProtocol.

    * Auto-resumes immediately on every ``wait_for_resume`` call.
    * Records every breakpoint hit so tests can assert on them.
    * ``wait_for_terminate`` blocks forever (never quits on its own).
    """

    def __init__(self, breakpoints: list[str] | Literal["*"]) -> None:
        self._breakpoints = breakpoints
        self.breakpoint_hits: list[UiPathBreakpointResult] = []
        self.completed_result: UiPathRuntimeResult | None = None
        self.state_updates: list[UiPathRuntimeStateEvent] = []
        self.errors: list[str] = []
        self.connected = False
        self.execution_started = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def emit_execution_started(self, **kwargs: Any) -> None:
        self.execution_started = True

    async def emit_state_update(self, state_event: UiPathRuntimeStateEvent) -> None:
        self.state_updates.append(state_event)

    async def emit_breakpoint_hit(
        self, breakpoint_result: UiPathBreakpointResult
    ) -> None:
        self.breakpoint_hits.append(breakpoint_result)

    async def emit_execution_suspended(
        self, runtime_result: UiPathRuntimeResult
    ) -> None:
        pass

    async def emit_execution_resumed(self, resume_data: Any) -> None:
        pass

    async def emit_execution_completed(
        self, runtime_result: UiPathRuntimeResult
    ) -> None:
        self.completed_result = runtime_result

    async def emit_execution_error(self, error: str) -> None:
        self.errors.append(error)

    async def wait_for_resume(self) -> Any:
        return None  # auto-resume

    async def wait_for_terminate(self) -> None:
        await asyncio.Event().wait()  # block forever

    def get_breakpoints(self) -> list[str] | Literal["*"]:
        return self._breakpoints


def _write_script(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content)
    return path


def _build_stack(
    script: Path,
    breakpoints: list[str] | Literal["*"],
    func_name: str = "main",
) -> tuple[UiPathDebugRuntime, MockDebugBridge]:
    """Build the full debug stack and return (runtime, bridge)."""
    inner = UiPathFunctionsRuntime(str(script), func_name, script.name)
    debug_fn = UiPathDebugFunctionsRuntime(
        inner, entrypoint_path=str(script), function_name=func_name
    )
    bridge = MockDebugBridge(breakpoints=breakpoints)
    runtime = UiPathDebugRuntime(delegate=debug_fn, debug_bridge=bridge)
    return runtime, bridge


class _FakeDebuggerTracer:
    """Stands in for the trace function of a pydevd-based debugger (debugpy, PyCharm)."""

    __module__ = "_pydevd_bundle.pydevd_fake"

    def __init__(self) -> None:
        self.called: list[str] = []

    def __call__(self, frame: FrameType, event: str, arg: Any) -> Any:
        if event == "call":
            self.called.append(frame.f_code.co_name)
        return self


@contextmanager
def _traced_by(tracer: _FakeDebuggerTracer) -> Iterator[None]:
    """Trace this thread and new threads with *tracer*, as pydevd does before Python 3.12."""
    previous = sys.gettrace()
    previous_for_new_threads = threading.gettrace()
    sys.settrace(tracer)
    threading.settrace(tracer)
    try:
        yield
    finally:
        # None clears the hook, but typeshed only accepts a trace function.
        threading.settrace(previous_for_new_threads)  # type: ignore[arg-type]
        sys.settrace(previous)


@pytest.fixture()
def script_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temp directory used as cwd so BreakpointController treats scripts as project files."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(tmp_path)
    return tmp_path


class TestBreakpointE2E:
    async def test_single_breakpoint_pauses_and_resumes(self, script_dir: Path):
        # Line 1: def main(input):
        # Line 2:     x = input.get("value", 10)
        # Line 3:     y = x * 2                     ← breakpoint
        # Line 4:     z = y + 5
        # Line 5:     return {"result": z}
        script = _write_script(
            script_dir,
            "calc.py",
            "def main(input):\n"
            '    x = input.get("value", 10)\n'
            "    y = x * 2\n"
            "    z = y + 5\n"
            '    return {"result": z}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["3"])

        try:
            result = await runtime.execute({"value": 7})

            assert len(bridge.breakpoint_hits) == 1
            hit = bridge.breakpoint_hits[0]
            assert hit.status == UiPathRuntimeStatus.SUSPENDED
            assert hit.breakpoint_type == "before"
            assert hit.current_state["x"] == 7

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 19}  # (7*2)+5

            assert bridge.execution_started
            assert bridge.completed_result is not None
        finally:
            await runtime.dispose()

    async def test_multiple_breakpoints_fire_in_order(self, script_dir: Path):
        # Line 1: def main(input):
        # Line 2:     a = 1
        # Line 3:     b = 2                   ← bp 1
        # Line 4:     c = a + b
        # Line 5:     d = c * 10              ← bp 2
        # Line 6:     return {"result": d}
        script = _write_script(
            script_dir,
            "multi.py",
            "def main(input):\n"
            "    a = 1\n"
            "    b = 2\n"
            "    c = a + b\n"
            "    d = c * 10\n"
            '    return {"result": d}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["3", "5"])

        try:
            result = await runtime.execute({})

            assert len(bridge.breakpoint_hits) == 2
            # bp1 @ line 3: a is set, b not yet
            assert bridge.breakpoint_hits[0].current_state["a"] == 1
            assert "b" not in bridge.breakpoint_hits[0].current_state
            # bp2 @ line 5: a, b, c set; d not yet
            assert bridge.breakpoint_hits[1].current_state["c"] == 3
            assert "d" not in bridge.breakpoint_hits[1].current_state

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 30}
        finally:
            await runtime.dispose()

    async def test_step_mode_breaks_every_line(self, script_dir: Path):
        script = _write_script(
            script_dir,
            "steps.py",
            'def main(input):\n    x = 1\n    y = 2\n    return {"sum": x + y}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({})

            # Lines 2, 3, 4 — each executable statement
            assert len(bridge.breakpoint_hits) >= 3
            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"sum": 3}
        finally:
            await runtime.dispose()

    async def test_file_colon_line_breakpoint_format(self, script_dir: Path):
        # Line 1: def main(input):
        # Line 2:     msg = "hello"
        # Line 3:     return {"message": msg}     ← bp via "qualified.py:3"
        script = _write_script(
            script_dir,
            "qualified.py",
            'def main(input):\n    msg = "hello"\n    return {"message": msg}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["qualified.py:3"])

        try:
            result = await runtime.execute({})

            assert len(bridge.breakpoint_hits) == 1
            assert bridge.breakpoint_hits[0].current_state["msg"] == "hello"
            assert result.output == {"message": "hello"}
        finally:
            await runtime.dispose()

    async def test_no_breakpoints_completes_immediately(self, script_dir: Path):
        script = _write_script(
            script_dir,
            "passthrough.py",
            'def main(input):\n    return {"ok": True}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=[])

        try:
            result = await runtime.execute({})

            assert len(bridge.breakpoint_hits) == 0
            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"ok": True}
            assert bridge.completed_result is not None
        finally:
            await runtime.dispose()

    async def test_breakpoint_captures_complex_locals(self, script_dir: Path):
        # Line 5 breakpoint — items, mapping, obj all set; total not yet
        script = _write_script(
            script_dir,
            "locals_test.py",
            "def main(input):\n"
            "    items = [1, 2, 3]\n"
            '    mapping = {"key": "value"}\n'
            "    obj = object()\n"
            "    total = sum(items)\n"
            '    return {"total": total}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["5"])

        try:
            result = await runtime.execute({})

            assert len(bridge.breakpoint_hits) == 1
            state = bridge.breakpoint_hits[0].current_state
            assert state["items"] == [1, 2, 3]
            assert state["mapping"] == {"key": "value"}
            assert isinstance(state["obj"], str)
            assert "object" in state["obj"]
            assert result.output == {"total": 6}
        finally:
            await runtime.dispose()

    async def test_breakpoint_in_nested_function(self, script_dir: Path):
        # bp on nested.py:3 → inside helper(), doubled should be set
        script = _write_script(
            script_dir,
            "nested.py",
            "def helper(n):\n"
            "    doubled = n * 2\n"
            "    return doubled\n"
            "\n"
            "def main(input):\n"
            '    val = input.get("n", 5)\n'
            "    result = helper(val)\n"
            '    return {"result": result}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["nested.py:3"])

        try:
            result = await runtime.execute({"n": 4})

            assert len(bridge.breakpoint_hits) == 1
            assert bridge.breakpoint_hits[0].current_state["doubled"] == 8
            assert result.output == {"result": 8}
        finally:
            await runtime.dispose()

    async def test_breakpoint_node_format(self, script_dir: Path):
        script = _write_script(
            script_dir,
            "node_fmt.py",
            'def main(input):\n    x = 42\n    return {"x": x}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["2"])

        try:
            await runtime.execute({})

            assert len(bridge.breakpoint_hits) == 1
            node = bridge.breakpoint_hits[0].breakpoint_node
            assert "node_fmt.py" in node
            assert ":2" in node
        finally:
            await runtime.dispose()

    async def test_breakpoint_reports_the_paused_function_start_line(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "starts.py",
            "def helper(n):\n"
            "    doubled = n * 2\n"
            "    return doubled\n"
            "\n"
            "def main(input):\n"
            '    result = helper(input["n"])\n'
            '    return {"result": result}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["3", "7"])

        try:
            await runtime.execute({"n": 4})

            assert [hit.metadata for hit in bridge.breakpoint_hits] == [
                {"function_start_line": 1},
                {"function_start_line": 5},
            ]
        finally:
            await runtime.dispose()

    async def test_decorated_function_starts_at_its_first_decorator(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "decorated.py",
            "def registered(fn):\n"
            "    return fn\n"
            "\n"
            "@registered\n"
            "def main(input):\n"
            '    return {"n": input["n"]}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["6"])

        try:
            await runtime.execute({"n": 4})

            assert [hit.metadata for hit in bridge.breakpoint_hits] == [
                {"function_start_line": 4}
            ]
        finally:
            await runtime.dispose()

    async def test_bridge_lifecycle_events(self, script_dir: Path):
        """connect / emit_execution_started / emit_execution_completed / disconnect all fire."""
        script = _write_script(
            script_dir,
            "lifecycle.py",
            'def main(input):\n    return {"done": True}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=[])

        try:
            await runtime.execute({})

            assert bridge.execution_started
            assert bridge.completed_result is not None
            assert bridge.completed_result.status == UiPathRuntimeStatus.SUCCESSFUL
        finally:
            await runtime.dispose()
            assert not bridge.connected  # disconnect called by dispose

    async def test_bridge_receives_breakpoint_then_completion(self, script_dir: Path):
        """Bridge sees emit_breakpoint_hit followed by emit_execution_completed."""
        script = _write_script(
            script_dir,
            "bpcomp.py",
            'def main(input):\n    x = 1\n    return {"x": x}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["2"])

        try:
            result = await runtime.execute({})

            assert len(bridge.breakpoint_hits) == 1
            assert bridge.completed_result is not None
            assert bridge.completed_result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"x": 1}
        finally:
            await runtime.dispose()

    async def test_stream_yields_breakpoint_and_result_events(self, script_dir: Path):
        """Streaming the debug runtime yields breakpoint events then the final result."""
        script = _write_script(
            script_dir,
            "stream_test.py",
            'def main(input):\n    a = 10\n    b = 20\n    return {"sum": a + b}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["3"])

        try:
            events = []
            async for event in runtime.stream({}):
                events.append(event)

            bp_events = [e for e in events if isinstance(e, UiPathBreakpointResult)]
            result_events = [
                e
                for e in events
                if isinstance(e, UiPathRuntimeResult)
                and not isinstance(e, UiPathBreakpointResult)
            ]

            assert len(bp_events) == 1
            assert bp_events[0].current_state["a"] == 10
            assert len(result_events) == 1
            assert result_events[0].output == {"sum": 30}
        finally:
            await runtime.dispose()


def _frame_in(path: Path) -> FrameType:
    """A frame of code compiled from *path*, paused at its return line (4)."""
    path.write_text("import sys\n\ndef capture():\n    return sys._getframe()\n")
    namespace: dict[str, Any] = {}
    exec(compile(path.read_text(), str(path), "exec"), namespace)
    return namespace["capture"]()


class _Loop:
    def __init__(self) -> None:
        self.scheduled: list[tuple[Any, tuple[Any, ...]]] = []

    def call_soon_threadsafe(self, callback: Any, *args: Any) -> None:
        self.scheduled.append((callback, args))


class _Task:
    def __init__(self, cancelling: int = 0) -> None:
        self.cancels = 0
        self._cancelling = cancelling

    def cancelling(self) -> int:
        return self._cancelling

    def cancel(self) -> bool:
        self.cancels += 1
        return True


class _Stopped:
    """A stopped controller whose execution runs ``function_task`` on a fake loop."""

    def __init__(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch, breakpoints=()
    ) -> None:
        self.controller = BreakpointController(
            project_dir=str(script_dir), breakpoints=list(breakpoints)
        )
        self.loop = _Loop()
        self.function_task = _Task()
        self.current: _Task | None = self.function_task
        self.controller._loop = cast(Any, self.loop)
        self.controller._task = cast(Any, self.function_task)
        monkeypatch.setattr(asyncio, "current_task", lambda loop=None: self.current)
        # The trace is called directly here, so it stays set when it raises.
        self.retraces: list[Any] = []
        monkeypatch.setattr(sys, "setprofile", self.retraces.append)
        self.controller.request_stop()

    def trace(self, frame: FrameType, event: str = "line", arg: Any = None) -> Any:
        return self.controller._trace_callback(frame, event, arg)


class TestBreakpointController:
    def test_a_stop_raises_once_per_task_and_in_project_code_only(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        stopped = _Stopped(script_dir, monkeypatch)
        project_frame = _frame_in(script_dir / "project.py")
        child = _Task()
        stopped.current = child

        assert stopped.trace(sys._getframe(), "call") is None
        # Also a coroutine's resumption: raising there would skip its handlers.
        assert (
            stopped.trace(project_frame, "call") == stopped.controller._trace_callback
        )
        with pytest.raises(asyncio.CancelledError):
            stopped.trace(project_frame)
        assert stopped.trace(project_frame) is None

        stopped.current = stopped.function_task
        with pytest.raises(asyncio.CancelledError):
            stopped.trace(project_frame)
        assert stopped.trace(project_frame) is None

        assert len(stopped.retraces) == 2

    def test_the_trace_is_set_again_at_the_next_call_after_it_raises(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        stopped = _Stopped(script_dir, monkeypatch)
        previous_profiler = object()
        monkeypatch.setattr(sys, "getprofile", lambda: previous_profiler)
        traces: list[Any] = []
        monkeypatch.setattr(sys, "settrace", traces.append)
        with pytest.raises(asyncio.CancelledError):
            stopped.trace(_frame_in(script_dir / "project.py"))
        [retrace] = stopped.retraces

        retrace(sys._getframe(), "call", None)

        assert traces == [stopped.controller._trace_callback]
        assert stopped.retraces == [retrace, previous_profiler]

    def test_a_stop_leaves_code_outside_the_execution_alone(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project_frame = _frame_in(script_dir / "project.py")
        before_the_loop = BreakpointController(
            project_dir=str(script_dir), breakpoints=[]
        )
        before_the_loop.request_stop()
        assert before_the_loop._trace_callback(project_frame, "line", None) is None

        stopped = _Stopped(script_dir, monkeypatch)
        stopped.current = None
        assert stopped.trace(project_frame) is None

    def test_a_task_with_a_cancellation_on_its_way_is_left_to_it(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        stopped = _Stopped(script_dir, monkeypatch)
        stopped.current = _Task(cancelling=1)

        project_frame = _frame_in(script_dir / "project.py")
        assert stopped.trace(project_frame) == stopped.controller._trace_callback

    def test_a_task_unwinding_the_stop_of_a_task_it_awaits_gets_no_other(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        stopped = _Stopped(script_dir, monkeypatch)
        project_frame = _frame_in(script_dir / "project.py")
        error = asyncio.CancelledError()

        assert (
            stopped.trace(project_frame, "exception", (type(error), error, None))
            is None
        )
        assert stopped.trace(project_frame) is None
        stopped.controller._cancel_task()
        assert stopped.function_task.cancels == 0

    def test_the_function_task_is_cancelled_once(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        stopped = _Stopped(script_dir, monkeypatch)
        stopped.current = _Task()
        with pytest.raises(asyncio.CancelledError):
            stopped.trace(_frame_in(script_dir / "project.py"))

        stopped.controller._cancel_task()
        stopped.controller._cancel_task()

        assert stopped.function_task.cancels == 1

    def test_a_task_the_stop_reached_ignores_cancellation(self, script_dir: Path):
        controller = BreakpointController(project_dir=str(script_dir), breakpoints=[])
        loop = asyncio.new_event_loop()
        try:
            loop.set_task_factory(_new_stop_once_task)
            stopped = loop.create_task(asyncio.sleep(0, "done"))
            running = loop.create_task(asyncio.sleep(1))
            controller._mark_stopped(stopped)

            assert not stopped.cancel()
            assert running.cancel()
            assert loop.run_until_complete(stopped) == "done"
            with pytest.raises(asyncio.CancelledError):
                loop.run_until_complete(running)
        finally:
            loop.close()

    def test_a_stop_while_paused_raises_at_the_breakpoint(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        frame = _frame_in(script_dir / "paused.py")
        stopped = _Stopped(
            script_dir, monkeypatch, breakpoints=[f"paused.py:{frame.f_lineno}"]
        )
        controller = stopped.controller
        controller._stopped = False

        class _StoppedWhilePaused:
            def wait(self) -> None:
                controller._stopped = True

            def clear(self) -> None:
                pass

            def set(self) -> None:
                pass

        monkeypatch.setattr(controller, "_resume_event", _StoppedWhilePaused())

        with pytest.raises(asyncio.CancelledError):
            stopped.trace(frame)
        assert controller._events.get_nowait()[0] == "breakpoint"

    def test_parse_bare_line_numbers(self, script_dir: Path):
        script = script_dir / "entry.py"
        script.write_text("x = 1\n")

        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=["5", "10"],
            entrypoint_path=str(script),
        )
        abspath = str(script.resolve())
        assert abspath in ctrl._file_breakpoints
        assert ctrl._file_breakpoints[abspath] == {5, 10}

    def test_parse_file_colon_line(self, script_dir: Path):
        script = script_dir / "foo.py"
        script.write_text("x = 1\n")

        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=["foo.py:7"],
        )
        abspath = str(script.resolve())
        assert abspath in ctrl._file_breakpoints
        assert 7 in ctrl._file_breakpoints[abspath]

    def test_step_mode(self, script_dir: Path):
        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints="*",
        )
        assert ctrl._step_mode is True
        assert ctrl._file_breakpoints == {}

    def test_update_breakpoints_replaces_set(self, script_dir: Path):
        script = script_dir / "up.py"
        script.write_text("x = 1\n")
        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=["3"],
            entrypoint_path=str(script),
        )
        abspath = str(script.resolve())
        assert ctrl._file_breakpoints[abspath] == {3}

        ctrl.update_breakpoints(["7", "9"])
        assert ctrl._file_breakpoints[abspath] == {7, 9}

    def test_update_to_step_mode(self, script_dir: Path):
        script = script_dir / "s.py"
        script.write_text("x = 1\n")
        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=["3"],
            entrypoint_path=str(script),
        )
        assert ctrl._step_mode is False

        ctrl.update_breakpoints("*")
        assert ctrl._step_mode is True
        assert ctrl._file_breakpoints == {}

    def test_invalid_breakpoint_strings_ignored(self, script_dir: Path):
        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=["not_a_number", "agent_node_name"],
        )
        assert ctrl._file_breakpoints == {}

    def test_is_project_file(self, script_dir: Path):
        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=[],
        )
        assert ctrl._is_project_file(str(script_dir / "main.py"))
        assert not ctrl._is_project_file(str(script_dir / "site-packages" / "lib.py"))
        assert not ctrl._is_project_file("/some/other/path/foo.py")

    def test_is_project_file_rejects_frozen_modules(self, script_dir: Path):
        """Frozen/built-in module paths must not pass the project-file check."""
        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=[],
        )
        # os.path.abspath("<frozen importlib._bootstrap>") resolves under cwd
        frozen_resolved = os.path.abspath("<frozen importlib._bootstrap_external>")
        assert not ctrl._is_project_file(frozen_resolved)


class TestStateEvents:
    """State events should fire only for call-graph functions."""

    async def test_state_events_emitted_for_graph_functions(self, script_dir: Path):
        """State events fire for the entrypoint and functions it calls."""
        _write_script(
            script_dir,
            "helpers.py",
            "def helper(n):\n    return n * 2\n",
        )
        script = _write_script(
            script_dir,
            "main.py",
            "from helpers import helper\n"
            "\n"
            "def main(input):\n"
            '    val = input.get("n", 5)\n'
            "    result = helper(val)\n"  # line 5
            '    return {"result": result}\n',
        )
        # Use step mode so the controller path is active and state events fire
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({"n": 3})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 6}

            # State events should include main and helper
            state_names = [s.node_name for s in bridge.state_updates]
            assert "main" in state_names
            assert "helper" in state_names
        finally:
            await runtime.dispose()

    async def test_state_events_not_emitted_for_external_functions(
        self, script_dir: Path
    ):
        """Functions from external modules (json, os, etc.) should NOT produce state events."""
        script = _write_script(
            script_dir,
            "main.py",
            "import json\n"
            "\n"
            "def main(input):\n"
            '    data = json.dumps({"hello": "world"})\n'  # line 4
            '    return {"data": data}\n',
        )
        # Step mode to activate the controller (and state events)
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL

            state_names = [s.node_name for s in bridge.state_updates]
            # Only main — json.dumps is external; 2 events: started + completed
            assert all(name == "main" for name in state_names)
            assert len(state_names) == 2
        finally:
            await runtime.dispose()

    async def test_state_events_carry_locals(self, script_dir: Path):
        """State event payload should contain the function's arguments."""
        script = _write_script(
            script_dir,
            "main.py",
            "def helper(x, y):\n"
            "    return x + y\n"
            "\n"
            "def main(input):\n"
            "    return helper(1, 2)\n",  # line 5
        )
        # Use a breakpoint to activate the controller path
        runtime, bridge = _build_stack(script, breakpoints=["5"])

        try:
            await runtime.execute({})

            helper_started = [
                s
                for s in bridge.state_updates
                if s.node_name == "helper"
                and s.phase == UiPathRuntimeStatePhase.STARTED
            ]
            helper_completed = [
                s
                for s in bridge.state_updates
                if s.node_name == "helper"
                and s.phase == UiPathRuntimeStatePhase.COMPLETED
            ]
            assert len(helper_started) == 1
            assert len(helper_completed) == 1
            # At call time, x and y should be in the payload
            assert helper_started[0].payload["x"] == 1
            assert helper_started[0].payload["y"] == 2
        finally:
            await runtime.dispose()

    async def test_state_events_with_breakpoints(self, script_dir: Path):
        """State events and breakpoints work together."""
        script = _write_script(
            script_dir,
            "main.py",
            "def helper():\n"
            "    return 42\n"
            "\n"
            "def main(input):\n"
            "    x = helper()\n"  # line 5
            '    return {"x": x}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["5"])

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"x": 42}

            # Should have both state updates and breakpoint hits
            assert len(bridge.breakpoint_hits) == 1
            state_names = [s.node_name for s in bridge.state_updates]
            assert "main" in state_names
        finally:
            await runtime.dispose()

    async def test_no_state_events_without_function_name(self, script_dir: Path):
        """When function_name is not provided, no state events fire (even with breakpoints)."""
        script = _write_script(
            script_dir,
            "main.py",
            'def main(input):\n    x = 1\n    return {"ok": True}\n',
        )
        inner = UiPathFunctionsRuntime(str(script), "main", script.name)
        # No function_name → no graph → no state events
        debug_fn = UiPathDebugFunctionsRuntime(inner, entrypoint_path=str(script))
        bridge = MockDebugBridge(breakpoints=["2"])
        runtime = UiPathDebugRuntime(delegate=debug_fn, debug_bridge=bridge)

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert len(bridge.breakpoint_hits) == 1
            assert len(bridge.state_updates) == 0
        finally:
            await runtime.dispose()

    async def test_state_events_emitted_without_breakpoints(self, script_dir: Path):
        """State events fire even without breakpoints when the call graph exists."""
        script = _write_script(
            script_dir,
            "main.py",
            "def helper():\n"
            "    return 42\n"
            "\n"
            "def main(input):\n"
            "    x = helper()\n"
            '    return {"x": x}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=[])

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"x": 42}

            # State events fire even with no breakpoints
            state_names = [s.node_name for s in bridge.state_updates]
            assert "main" in state_names
            assert "helper" in state_names
            # No breakpoints should have been hit
            assert len(bridge.breakpoint_hits) == 0
        finally:
            await runtime.dispose()

    async def test_multiline_expression_breakpoint_hits_once(self, script_dir: Path):
        """Breakpoint on a multiline call expression should fire exactly once.

        Python's bytecode bounces back to the call-site line after
        evaluating nested arguments on deeper lines, e.g.::

            return Wrapper(          # line 5 — LOAD_GLOBAL + CALL
                result=choice(       # line 6
                    [1, 2, 3]        # line 7
                )                    # ← CALL choice → back to line 6
            )                        # ← CALL Wrapper → back to line 5

        Without deduplication the breakpoint on line 5 fires twice.
        """
        script = _write_script(
            script_dir,
            "main.py",
            "import random\n"  # 1
            "\n"  # 2
            "async def get_random():\n"  # 3
            '    """Get a random value."""\n'  # 4
            "    return dict(\n"  # 5
            "        value=random.choice(\n"  # 6
            "            [1, 2, 3]\n"  # 7
            "        )\n"  # 8
            "    )\n"  # 9
            "\n"  # 10
            "async def main(input):\n"  # 11
            "    result = await get_random()\n"  # 12
            '    return {"result": result}\n',  # 13
        )
        # Breakpoint on line 5 — the first body line (multiline return)
        runtime, bridge = _build_stack(script, breakpoints=["main.py:5"])

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL

            # The breakpoint should fire exactly ONCE despite bytecode bouncing
            bp_nodes = [h.breakpoint_node for h in bridge.breakpoint_hits]
            assert len(bridge.breakpoint_hits) == 1, (
                f"Expected 1 breakpoint hit but got {len(bridge.breakpoint_hits)}: {bp_nodes}"
            )
        finally:
            await runtime.dispose()

    async def test_state_events_through_decorator_wrappers(self, script_dir: Path):
        """State events fire for functions wrapped with functools.wraps decorators.

        Simulates @traced-style decorators where the wrapper (sync_wrapper/
        async_wrapper) lives in an external module. The trace callback should
        still fire for the ORIGINAL function called from within the wrapper.
        """
        script = _write_script(
            script_dir,
            "main.py",
            "from functools import wraps\n"
            "\n"
            "def my_decorator(func):\n"
            "    @wraps(func)\n"
            "    def wrapper(*args, **kwargs):\n"
            "        return func(*args, **kwargs)\n"
            "    return wrapper\n"
            "\n"
            "@my_decorator\n"
            "def track_operator(op):\n"
            "    pass\n"
            "\n"
            "@my_decorator\n"
            "def apply_operator(op, a, b):\n"
            "    return a + b\n"
            "\n"
            "def main(input):\n"
            '    op = input.get("op", "+")\n'
            "    track_operator(op)\n"
            '    result = apply_operator(op, input.get("a", 1), input.get("b", 2))\n'
            '    return {"result": result}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({"a": 3, "b": 4})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 7}

            state_names = [s.node_name for s in bridge.state_updates]
            assert "main" in state_names
            assert "track_operator" in state_names
            assert "apply_operator" in state_names
        finally:
            await runtime.dispose()

    async def test_state_events_have_started_and_completed_phases(
        self, script_dir: Path
    ):
        """Each tracked function should emit both STARTED and COMPLETED phase events."""
        _write_script(
            script_dir,
            "phase_helpers.py",
            "def helper(n):\n    return n * 2\n",
        )
        script = _write_script(
            script_dir,
            "main.py",
            "from phase_helpers import helper\n"
            "\n"
            "def main(input):\n"
            '    val = input.get("n", 5)\n'
            "    result = helper(val)\n"
            '    return {"result": result}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({"n": 3})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 6}

            # Each tracked function (main, helper) should have started + completed
            for func_name in ("main", "helper"):
                started = [
                    s
                    for s in bridge.state_updates
                    if s.node_name == func_name
                    and s.phase == UiPathRuntimeStatePhase.STARTED
                ]
                completed = [
                    s
                    for s in bridge.state_updates
                    if s.node_name == func_name
                    and s.phase == UiPathRuntimeStatePhase.COMPLETED
                ]
                assert len(started) == 1, f"{func_name} should have 1 STARTED event"
                assert len(completed) == 1, f"{func_name} should have 1 COMPLETED event"

            # Completed events should carry __return__ key
            helper_completed = [
                s
                for s in bridge.state_updates
                if s.node_name == "helper"
                and s.phase == UiPathRuntimeStatePhase.COMPLETED
            ]
            assert "__return__" in helper_completed[0].payload
        finally:
            await runtime.dispose()

    async def test_stream_phase_events_from_functions_runtime(self, script_dir: Path):
        """UiPathFunctionsRuntime.stream() emits STARTED → COMPLETED → result."""
        script = _write_script(
            script_dir,
            "main.py",
            'def main(input):\n    return {"value": input.get("x", 0) + 1}\n',
        )
        inner = UiPathFunctionsRuntime(str(script), "main", script.name)

        try:
            events = []
            async for event in inner.stream({"x": 5}):
                events.append(event)

            # Should be: STARTED state event, COMPLETED state event, result
            state_events = [e for e in events if isinstance(e, UiPathRuntimeStateEvent)]
            result_events = [
                e
                for e in events
                if isinstance(e, UiPathRuntimeResult)
                and not isinstance(e, UiPathBreakpointResult)
            ]

            assert len(state_events) == 2
            assert state_events[0].phase == UiPathRuntimeStatePhase.STARTED
            assert state_events[0].payload == {"x": 5}
            assert state_events[1].phase == UiPathRuntimeStatePhase.COMPLETED
            assert state_events[1].payload == {"value": 6}

            assert len(result_events) == 1
            assert result_events[0].status == UiPathRuntimeStatus.SUCCESSFUL
            assert result_events[0].output == {"value": 6}
        finally:
            await inner.dispose()


class TestAttachedDebugger:
    """A debugger that traces through sys.settrace (debugpy before Python 3.12)."""

    async def test_debugger_keeps_tracing_the_function(self, script_dir: Path):
        """Without breakpoints of ours, the debugger's trace function sees every call."""
        _write_script(
            script_dir,
            "debugged_helpers.py",
            "def helper(n):\n    return n * 2\n",
        )
        script = _write_script(
            script_dir,
            "main.py",
            "from debugged_helpers import helper\n"
            "\n"
            "def main(input):\n"
            '    return {"result": helper(input["n"])}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=[])
        debugger = _FakeDebuggerTracer()

        try:
            with _traced_by(debugger):
                result = await runtime.execute({"n": 3})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 6}
            assert {"main", "helper"} <= set(debugger.called)
        finally:
            await runtime.dispose()

    async def test_breakpoints_of_ours_still_pause(self, script_dir: Path):
        """Breakpoints requested through the debug bridge still pause the function."""
        script = _write_script(
            script_dir,
            "calc.py",
            "def main(input):\n"
            '    x = input["value"]\n'
            "    y = x * 2\n"
            '    return {"result": y}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["3"])

        try:
            with _traced_by(_FakeDebuggerTracer()):
                result = await runtime.execute({"value": 4})

            assert len(bridge.breakpoint_hits) == 1
            assert bridge.breakpoint_hits[0].current_state["x"] == 4
            assert result.output == {"result": 8}
        finally:
            await runtime.dispose()

    async def test_warns_that_breakpoints_of_ours_replace_the_debugger(
        self,
        script_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ):
        """Breakpoints of ours take the function's thread from the debugger, so say so."""
        monkeypatch.setattr(
            "uipath.functions.debug._is_debugger_tracer", lambda tracer: True
        )
        script = _write_script(
            script_dir,
            "calc.py",
            "def main(input):\n"
            '    x = input["value"]\n'
            "    y = x * 2\n"
            '    return {"result": y}\n',
        )
        runtime, _ = _build_stack(script, breakpoints=["3"])
        # CLI tests leave the uipath logger with propagate = False, so attach
        # caplog's handler to the module logger itself.
        logger = logging.getLogger("uipath.functions.debug")
        logger.addHandler(caplog.handler)

        try:
            await runtime.execute({"value": 4})
        finally:
            logger.removeHandler(caplog.handler)
            await runtime.dispose()

        assert any(
            record.levelno == logging.WARNING
            and "debugger's breakpoints won't be hit" in record.getMessage()
            for record in caplog.records
        )

    async def test_no_call_graph_state_events_while_a_debugger_traces(
        self, script_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Call-graph state events need our trace function, so they are skipped."""
        monkeypatch.setattr(
            "uipath.functions.debug._is_debugger_tracer", lambda tracer: True
        )
        _write_script(
            script_dir,
            "skipped_helpers.py",
            "def helper(n):\n    return n + 1\n",
        )
        script = _write_script(
            script_dir,
            "main.py",
            "from skipped_helpers import helper\n"
            "\n"
            "def main(input):\n"
            '    return {"result": helper(input["n"])}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=[])

        try:
            result = await runtime.execute({"n": 1})

            assert result.output == {"result": 2}
            assert "helper" not in [s.node_name for s in bridge.state_updates]
        finally:
            await runtime.dispose()

    def test_recognizes_pydevd_trace_functions(self):
        def trace_dispatch(frame: FrameType, event: str, arg: Any) -> None:
            return None

        trace_dispatch.__module__ = "_pydevd_bundle.pydevd_trace_dispatch_regular"

        assert _is_debugger_tracer(_FakeDebuggerTracer())  # Cython build: an object
        assert _is_debugger_tracer(trace_dispatch)  # pure-Python build: a function

    def test_ignores_other_trace_functions(self):
        def coverage_tracer(frame: FrameType, event: str, arg: Any) -> None:
            return None

        coverage_tracer.__module__ = "coverage.pytracer"

        assert not _is_debugger_tracer(None)
        assert not _is_debugger_tracer(coverage_tracer)


def _functions_runtime(script: Path) -> UiPathDebugFunctionsRuntime:
    inner = UiPathFunctionsRuntime(str(script), "main", script.name)
    return UiPathDebugFunctionsRuntime(
        inner, entrypoint_path=str(script), function_name="main"
    )


async def _wait_until(path: Path, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not path.exists():
        assert loop.time() < deadline, f"{path.name} never appeared"
        await asyncio.sleep(0.01)


async def _assert_no_more_writes(path: Path) -> None:
    before = path.read_text()
    await asyncio.sleep(0.1)
    assert path.read_text() == before


class TestStoppingTheExecution:
    """Stopping the stream ends the function before the stream is done closing."""

    async def test_closing_the_stream_stops_a_running_function(self, script_dir: Path):
        script = _write_script(
            script_dir,
            "ticker.py",
            "import time\n"
            "from pathlib import Path\n"
            "\n"
            "def tick(n):\n"
            '    Path("ticks.txt").write_text(str(n))\n'
            "\n"
            "def main(input):\n"
            "    n = 0\n"
            "    while True:\n"
            "        n += 1\n"
            "        tick(n)\n"
            "        time.sleep(0.01)\n",
        )
        debug_fn = _functions_runtime(script)
        events = debug_fn.stream({})
        try:
            ticks = 0
            async for event in events:
                if (
                    isinstance(event, UiPathRuntimeStateEvent)
                    and event.node_name == "tick"
                ):
                    ticks += 1
                    if ticks == 3:
                        break
            controller = debug_fn._controller
            assert controller is not None

            await asyncio.wait_for(events.aclose(), timeout=5)

            assert controller._thread is not None
            assert not controller._thread.is_alive()
            await _assert_no_more_writes(script_dir / "ticks.txt")
        finally:
            await debug_fn.dispose()

    async def test_cancelling_the_consumer_stops_a_running_function(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "loop.py",
            "import time\n"
            "from pathlib import Path\n"
            "\n"
            "def main(input):\n"
            "    n = 0\n"
            "    while True:\n"
            "        n += 1\n"
            '        Path("ticks.txt").write_text(str(n))\n'
            "        time.sleep(0.01)\n",
        )
        debug_fn = _functions_runtime(script)

        async def consume() -> None:
            async for _event in debug_fn.stream({}):
                pass

        consumer = asyncio.create_task(consume())
        try:
            await _wait_until(script_dir / "ticks.txt")
            controller = debug_fn._controller
            assert controller is not None

            consumer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(consumer, timeout=5)

            assert controller._thread is not None
            assert not controller._thread.is_alive()
            await _assert_no_more_writes(script_dir / "ticks.txt")
        finally:
            await debug_fn.dispose()

    async def test_closing_the_stream_stops_an_async_function_where_it_awaits(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "waiter.py",
            "import asyncio\n"
            "from pathlib import Path\n"
            "\n"
            "async def main(input):\n"
            '    Path("started.txt").write_text("1")\n'
            "    await asyncio.sleep(30)\n"
            '    Path("finished.txt").write_text("1")\n',
        )
        debug_fn = _functions_runtime(script)
        events = debug_fn.stream({})
        try:
            async for _event in events:
                break
            await _wait_until(script_dir / "started.txt")
            controller = debug_fn._controller
            assert controller is not None

            await asyncio.wait_for(events.aclose(), timeout=5)

            assert controller._thread is not None
            assert not controller._thread.is_alive()
            assert not (script_dir / "finished.txt").exists()
        finally:
            await debug_fn.dispose()

    async def test_dispose_stops_a_function_paused_at_a_breakpoint(
        self, script_dir: Path
    ):
        # Line 4: x = 1
        # Line 5: Path("after.txt").write_text("ran")   <- breakpoint
        script = _write_script(
            script_dir,
            "paused.py",
            "from pathlib import Path\n"
            "\n"
            "def main(input):\n"
            "    x = 1\n"
            '    Path("after.txt").write_text("ran")\n'
            '    return {"x": x}\n',
        )
        debug_fn = _functions_runtime(script)
        events = [
            event
            async for event in debug_fn.stream(
                {}, UiPathStreamOptions(breakpoints=["5"])
            )
        ]
        assert isinstance(events[-1], UiPathBreakpointResult)
        controller = debug_fn._controller
        assert controller is not None

        await debug_fn.dispose()

        assert controller._thread is not None
        assert not controller._thread.is_alive()
        assert not (script_dir / "after.txt").exists()


class TestStopEdgeCases:
    """A stop reaches all of the project's code, is delivered once, and is waited out."""

    async def test_closing_the_stream_stops_a_loop_outside_the_call_graph(
        self, script_dir: Path
    ):
        _write_script(
            script_dir,
            "spin_helper.py",
            "def spin():\n    n = 0\n    while True:\n        n += 1\n",
        )
        script = _write_script(
            script_dir,
            "dynamic.py",
            "from pathlib import Path\n"
            "import spin_helper\n"
            "\n"
            "def main(input):\n"
            '    Path("started.txt").write_text("1")\n'
            '    getattr(spin_helper, "spin")()\n',
        )
        debug_fn = _functions_runtime(script)
        events = debug_fn.stream({})
        try:
            async for _event in events:
                break
            await _wait_until(script_dir / "started.txt")
            controller = debug_fn._controller
            assert controller is not None

            await asyncio.wait_for(events.aclose(), timeout=5)

            assert controller._thread is not None
            assert not controller._thread.is_alive()
        finally:
            await debug_fn.dispose()

    async def test_closing_the_stream_lets_an_awaiting_function_finish_its_cleanup(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "awaiting_cleanup.py",
            "import asyncio\n"
            "from pathlib import Path\n"
            "\n"
            "async def main(input):\n"
            "    try:\n"
            '        Path("started.txt").write_text("1")\n'
            "        await asyncio.sleep(30)\n"
            "    finally:\n"
            '        Path("cleanup_started.txt").write_text("1")\n'
            "        await asyncio.sleep(0.01)\n"
            '        Path("cleanup_done.txt").write_text("1")\n',
        )
        debug_fn = _functions_runtime(script)
        events = debug_fn.stream({})
        try:
            async for _event in events:
                break
            await _wait_until(script_dir / "started.txt")

            await asyncio.wait_for(events.aclose(), timeout=5)

            assert (script_dir / "cleanup_started.txt").exists()
            assert (script_dir / "cleanup_done.txt").exists()
        finally:
            await debug_fn.dispose()

    async def test_a_stop_in_running_code_lets_its_async_cleanup_finish(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "running_cleanup.py",
            "import asyncio\n"
            "import time\n"
            "from pathlib import Path\n"
            "\n"
            "async def main(input):\n"
            "    try:\n"
            '        Path("started.txt").write_text("1")\n'
            "        while True:\n"
            "            time.sleep(0.01)\n"
            "    finally:\n"
            '        Path("cleanup_started.txt").write_text("1")\n'
            "        await asyncio.sleep(0.01)\n"
            '        Path("cleanup_done.txt").write_text("1")\n',
        )
        debug_fn = _functions_runtime(script)
        events = debug_fn.stream({})
        try:
            async for _event in events:
                break
            await _wait_until(script_dir / "started.txt")

            await asyncio.wait_for(events.aclose(), timeout=5)

            assert (script_dir / "cleanup_started.txt").exists()
            assert (script_dir / "cleanup_done.txt").exists()
        finally:
            await debug_fn.dispose()

    async def test_cancelling_the_close_still_waits_for_the_function(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "blocking.py",
            "import time\n"
            "from pathlib import Path\n"
            "\n"
            "def main(input):\n"
            '    Path("started.txt").write_text("1")\n'
            "    time.sleep(1.0)\n"
            '    Path("finished.txt").write_text("1")\n',
        )
        debug_fn = _functions_runtime(script)
        events = debug_fn.stream({})
        try:
            async for _event in events:
                break
            await _wait_until(script_dir / "started.txt")
            controller = debug_fn._controller
            assert controller is not None
            # Let it get past its marker and into the blocking call.
            await asyncio.sleep(0.2)

            closer = asyncio.create_task(events.aclose())
            await asyncio.sleep(0.05)
            closer.cancel()
            done, _ = await asyncio.wait({closer}, timeout=5)
            assert closer in done
            assert closer.cancelled()

            assert controller._thread is not None
            assert not controller._thread.is_alive()
            assert not (script_dir / "finished.txt").exists()
        finally:
            await debug_fn.dispose()


class TestStoppingConcurrentCode:
    """A stop that reaches one of the function's tasks ends the function too."""

    async def test_a_stop_at_a_breakpoint_in_a_task_group_child_stops_the_parent(
        self, script_dir: Path
    ):
        # Line 5: x = 1   <- breakpoint, in the child task
        script = _write_script(
            script_dir,
            "group.py",
            "import asyncio\n"
            "from pathlib import Path\n"
            "\n"
            "async def child():\n"
            "    x = 1\n"
            "    return x\n"
            "\n"
            "async def main(input):\n"
            "    async with asyncio.TaskGroup() as tg:\n"
            "        tg.create_task(child())\n"
            '    Path("after.txt").write_text("ran")\n',
        )
        debug_fn = _functions_runtime(script)
        events = [
            event
            async for event in debug_fn.stream(
                {}, UiPathStreamOptions(breakpoints=["5"])
            )
        ]
        assert isinstance(events[-1], UiPathBreakpointResult)
        controller = debug_fn._controller
        assert controller is not None

        await debug_fn.dispose()

        assert controller._thread is not None
        assert not controller._thread.is_alive()
        assert not (script_dir / "after.txt").exists()

    async def test_a_task_group_child_finishes_its_cleanup_before_the_parent_stops(
        self, script_dir: Path
    ):
        # Line 6: x = 1   <- breakpoint, in the child task
        script = _write_script(
            script_dir,
            "group_cleanup.py",
            "import asyncio\n"
            "from pathlib import Path\n"
            "\n"
            "async def child():\n"
            "    try:\n"
            "        x = 1\n"
            "        return x\n"
            "    finally:\n"
            '        Path("cleanup_started.txt").write_text("1")\n'
            "        await asyncio.sleep(0.01)\n"
            '        Path("cleanup_done.txt").write_text("1")\n'
            "\n"
            "async def main(input):\n"
            "    async with asyncio.TaskGroup() as tg:\n"
            "        tg.create_task(child())\n"
            '    Path("after.txt").write_text("ran")\n',
        )
        debug_fn = _functions_runtime(script)
        events = [
            event
            async for event in debug_fn.stream(
                {}, UiPathStreamOptions(breakpoints=["6"])
            )
        ]
        assert isinstance(events[-1], UiPathBreakpointResult)

        await debug_fn.dispose()

        assert (script_dir / "cleanup_started.txt").exists()
        assert (script_dir / "cleanup_done.txt").exists()
        assert not (script_dir / "after.txt").exists()

    async def test_a_parent_resuming_during_a_stopped_childs_cleanup_waits_for_it(
        self, script_dir: Path
    ):
        # Line 6: x = 1   <- breakpoint, in the child task. The parent's next
        # step is already queued, so it resumes while the child cleans up.
        script = _write_script(
            script_dir,
            "group_parent_resumes.py",
            "import asyncio\n"
            "from pathlib import Path\n"
            "\n"
            "async def child():\n"
            "    try:\n"
            "        x = 1\n"
            "        return x\n"
            "    finally:\n"
            '        Path("cleanup_started.txt").write_text("1")\n'
            "        await asyncio.sleep(0.2)\n"
            '        Path("cleanup_done.txt").write_text("1")\n'
            "\n"
            "async def main(input):\n"
            "    try:\n"
            "        async with asyncio.TaskGroup() as tg:\n"
            "            tg.create_task(child())\n"
            "            await asyncio.sleep(0)\n"
            '            Path("parent_body.txt").write_text("1")\n'
            "    finally:\n"
            '        Path("parent_cleanup.txt").write_text("1")\n',
        )
        debug_fn = _functions_runtime(script)
        events = [
            event
            async for event in debug_fn.stream(
                {}, UiPathStreamOptions(breakpoints=["6"])
            )
        ]
        assert isinstance(events[-1], UiPathBreakpointResult)

        await debug_fn.dispose()

        assert (script_dir / "cleanup_started.txt").exists()
        assert (script_dir / "cleanup_done.txt").exists()
        assert not (script_dir / "parent_body.txt").exists()
        assert (script_dir / "parent_cleanup.txt").exists()

    async def test_a_parent_awaiting_a_stopped_child_gets_the_stop_once(
        self, script_dir: Path
    ):
        # Line 5: x = 1   <- breakpoint, in the child task
        script = _write_script(
            script_dir,
            "awaited_child.py",
            "import asyncio\n"
            "from pathlib import Path\n"
            "\n"
            "async def child():\n"
            "    x = 1\n"
            "    return x\n"
            "\n"
            "async def main(input):\n"
            "    try:\n"
            "        await asyncio.create_task(child())\n"
            '        Path("after.txt").write_text("ran")\n'
            "    finally:\n"
            '        Path("cleanup_started.txt").write_text("1")\n'
            "        await asyncio.sleep(0.01)\n"
            '        Path("cleanup_done.txt").write_text("1")\n',
        )
        debug_fn = _functions_runtime(script)
        events = [
            event
            async for event in debug_fn.stream(
                {}, UiPathStreamOptions(breakpoints=["5"])
            )
        ]
        assert isinstance(events[-1], UiPathBreakpointResult)

        await debug_fn.dispose()

        assert not (script_dir / "after.txt").exists()
        assert (script_dir / "cleanup_started.txt").exists()
        assert (script_dir / "cleanup_done.txt").exists()

    async def test_closing_the_stream_stops_a_busy_task_group_and_its_idle_tasks(
        self, script_dir: Path
    ):
        script = _write_script(
            script_dir,
            "group_spin.py",
            "import asyncio\n"
            "from pathlib import Path\n"
            "\n"
            "async def spin():\n"
            '    Path("started.txt").write_text("1")\n'
            "    n = 0\n"
            "    while True:\n"
            "        n += 1\n"
            "\n"
            "async def idle():\n"
            "    await asyncio.Event().wait()\n"
            "\n"
            "async def main(input):\n"
            "    async with asyncio.TaskGroup() as tg:\n"
            "        tg.create_task(idle())\n"
            "        tg.create_task(spin())\n"
            '    Path("after.txt").write_text("ran")\n',
        )
        debug_fn = _functions_runtime(script)
        events = debug_fn.stream({})
        try:
            async for _event in events:
                break
            await _wait_until(script_dir / "started.txt")
            controller = debug_fn._controller
            assert controller is not None

            await asyncio.wait_for(events.aclose(), timeout=5)

            assert controller._thread is not None
            assert not controller._thread.is_alive()
            assert not (script_dir / "after.txt").exists()
        finally:
            await debug_fn.dispose()
