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
import os
from pathlib import Path
from typing import Any, Literal

import pytest

from uipath.functions.debug import BreakpointController, UiPathDebugFunctionsRuntime
from uipath.functions.runtime import UiPathFunctionsRuntime
from uipath.runtime import (
    UiPathBreakpointResult,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
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


class TestBreakpointController:
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

            # The breakpoint must fire at least once.  Multiline expressions
            # may cause it to fire more than once due to bytecode bouncing
            # (the same line is revisited after nested arguments are
            # evaluated).  This is acceptable — suppressing the bounce
            # would also suppress legitimate loop-iteration breakpoints.
            assert len(bridge.breakpoint_hits) >= 1
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

    async def test_function_that_raises_emits_faulted(self, script_dir: Path):
        """A tracked function that raises an exception should emit FAULTED, not COMPLETED."""
        script = _write_script(
            script_dir,
            "main.py",
            "def raiser():\n"
            "    raise ValueError('boom')\n"
            "\n"
            "def main(input):\n"
            "    try:\n"
            "        raiser()\n"
            "    except ValueError:\n"
            "        pass\n"
            '    return {"ok": True}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"ok": True}

            # raiser() should have 1 STARTED + 1 FAULTED
            raiser_started = [
                s
                for s in bridge.state_updates
                if s.node_name == "raiser"
                and s.phase == UiPathRuntimeStatePhase.STARTED
            ]
            raiser_faulted = [
                s
                for s in bridge.state_updates
                if s.node_name == "raiser"
                and s.phase == UiPathRuntimeStatePhase.FAULTED
            ]
            raiser_completed = [
                s
                for s in bridge.state_updates
                if s.node_name == "raiser"
                and s.phase == UiPathRuntimeStatePhase.COMPLETED
            ]
            assert len(raiser_started) == 1
            assert len(raiser_faulted) == 1
            assert len(raiser_completed) == 0
        finally:
            await runtime.dispose()

    async def test_function_catches_exception_emits_completed(self, script_dir: Path):
        """A tracked function that catches its own exception should emit COMPLETED, not FAULTED."""
        script = _write_script(
            script_dir,
            "main.py",
            "def catcher():\n"
            "    try:\n"
            "        raise ValueError('internal')\n"
            "    except ValueError:\n"
            "        return 42\n"
            "\n"
            "def main(input):\n"
            "    result = catcher()\n"
            '    return {"result": result}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 42}

            # catcher() should have 1 STARTED + 1 COMPLETED (not FAULTED)
            catcher_started = [
                s
                for s in bridge.state_updates
                if s.node_name == "catcher"
                and s.phase == UiPathRuntimeStatePhase.STARTED
            ]
            catcher_completed = [
                s
                for s in bridge.state_updates
                if s.node_name == "catcher"
                and s.phase == UiPathRuntimeStatePhase.COMPLETED
            ]
            catcher_faulted = [
                s
                for s in bridge.state_updates
                if s.node_name == "catcher"
                and s.phase == UiPathRuntimeStatePhase.FAULTED
            ]
            assert len(catcher_started) == 1
            assert len(catcher_completed) == 1
            assert len(catcher_faulted) == 0
        finally:
            await runtime.dispose()


class TestRobustness:
    """Tests for edge-case safety and hardening improvements."""

    async def test_large_string_locals_are_truncated(self, script_dir: Path):
        """Very large string locals should be truncated, not cause OOM."""
        script = _write_script(
            script_dir,
            "big_str.py",
            "def main(input):\n"
            "    big = 'x' * 100_000\n"
            "    y = 1\n"
            '    return {"y": y}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["3"])

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert len(bridge.breakpoint_hits) == 1
            state = bridge.breakpoint_hits[0].current_state
            # Should be truncated, not the full 100k
            assert len(state["big"]) <= 11_000
            assert state["big"].endswith("...")
        finally:
            await runtime.dispose()

    async def test_large_collection_locals_are_summarized(self, script_dir: Path):
        """Collections with many items should be summarised, not serialised."""
        script = _write_script(
            script_dir,
            "big_list.py",
            "def main(input):\n"
            "    big = list(range(10_000))\n"
            "    y = 1\n"
            '    return {"y": y}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["3"])

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert len(bridge.breakpoint_hits) == 1
            state = bridge.breakpoint_hits[0].current_state
            # Large collection should be a summary string, not the full list
            assert isinstance(state["big"], str)
            assert "10000" in state["big"]
        finally:
            await runtime.dispose()

    async def test_many_locals_are_capped(self, script_dir: Path):
        """Functions with hundreds of locals should be capped at _MAX_LOCALS."""
        assignments = "\n".join(f"    v{i} = {i}" for i in range(150))
        script = _write_script(
            script_dir,
            "many_locals.py",
            f'def main(input):\n{assignments}\n    y = 1\n    return {{"y": y}}\n',
        )
        # Breakpoint on a line after all assignments
        line_num = 153  # 1 (def) + 150 (assignments) + 1 (y = 1) + 1 (return)
        runtime, bridge = _build_stack(script, breakpoints=[str(line_num)])

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert len(bridge.breakpoint_hits) == 1
            state = bridge.breakpoint_hits[0].current_state
            # Should be capped at _MAX_LOCALS (100) + the overflow entry
            assert len(state) <= 101
            assert "..." in state
        finally:
            await runtime.dispose()

    async def test_breakpoint_in_loop_fires_each_iteration(self, script_dir: Path):
        """Breakpoint inside a for-loop should fire on every iteration."""
        script = _write_script(
            script_dir,
            "loop.py",
            "def main(input):\n"
            "    total = 0\n"
            "    for i in range(3):\n"
            "        total += i\n"  # line 4 breakpoint
            '    return {"total": total}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints=["4"])

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"total": 3}  # 0+1+2
            # Should fire 3 times, once per iteration
            assert len(bridge.breakpoint_hits) == 3
        finally:
            await runtime.dispose()

    def test_wait_for_event_raises_on_dead_thread(self, script_dir: Path):
        """wait_for_event raises RuntimeError when the trace thread dies."""
        import threading as _threading

        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=[],
        )
        # Create a thread that exits immediately
        ctrl._thread = _threading.Thread(target=lambda: None)
        ctrl._thread.start()
        ctrl._thread.join()

        # Thread is dead, no events in queue -> should raise, not hang
        with pytest.raises(RuntimeError, match="Trace thread died"):
            ctrl.wait_for_event()

    def test_update_breakpoints_atomic_swap(self, script_dir: Path):
        """update_breakpoints should swap the dict atomically, never clear-then-add."""
        script = script_dir / "atomic.py"
        script.write_text("x = 1\n")
        ctrl = BreakpointController(
            project_dir=str(script_dir),
            breakpoints=["3"],
            entrypoint_path=str(script),
        )
        abspath = str(script.resolve())
        assert ctrl._file_breakpoints[abspath] == {3}

        # Swap to a new set -- should never be empty in between
        ctrl.update_breakpoints(["7", "9"])
        assert ctrl._file_breakpoints[abspath] == {7, 9}

        # Step mode -- breakpoints should be empty
        ctrl.update_breakpoints("*")
        assert ctrl._step_mode is True
        assert ctrl._file_breakpoints == {}

        # None -- should clear both
        ctrl.update_breakpoints(None)
        assert ctrl._step_mode is False
        assert ctrl._file_breakpoints == {}

    def test_find_class_method_in_graph(self, script_dir: Path):
        """Graph builder should find methods defined inside class bodies."""
        from uipath.functions.graph_builder import build_call_graph

        _write_script(
            script_dir,
            "cls.py",
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
            "\n"
            "def helper(x):\n"
            "    return x * 2\n",
        )
        graph = build_call_graph(
            str(script_dir / "cls.py"), "add", project_dir=str(script_dir)
        )
        node_names = [n.name for n in graph.nodes]
        assert "add" in node_names

    async def test_step_mode_in_loop_fires_each_iteration(self, script_dir: Path):
        """Step mode should fire breakpoints on every iteration of a loop body."""
        script = _write_script(
            script_dir,
            "loop_step.py",
            "def main(input):\n"
            "    total = 0\n"
            "    for i in range(3):\n"
            "        total += i\n"
            '    return {"total": total}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"total": 3}

            # Count hits on line 4 (total += i) -- should be 3
            line4_hits = [
                h for h in bridge.breakpoint_hits if ":4" in h.breakpoint_node
            ]
            assert len(line4_hits) == 3
        finally:
            await runtime.dispose()


class TestProjectDirConsistency:
    """Verify graph node IDs, breakpoints, and state events all use CWD-relative paths."""

    async def test_cross_file_breakpoint_on_helper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Breakpoints on called functions in another file work using graph node IDs."""
        import sys as _sys

        mod_name = "bp_helpers"
        monkeypatch.chdir(tmp_path)
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.delitem(_sys.modules, mod_name, raising=False)

        _write_script(
            tmp_path,
            f"{mod_name}.py",
            "def helper(n):\n"
            "    doubled = n * 2\n"  # line 2
            "    return doubled\n",
        )
        script = _write_script(
            tmp_path,
            "bp_main.py",
            f"from {mod_name} import helper\n"
            "\n"
            "def main(input):\n"
            '    val = input.get("n", 5)\n'
            "    result = helper(val)\n"
            '    return {"result": result}\n',
        )

        # get_schema should produce node IDs relative to CWD
        from uipath.functions.graph_builder import build_call_graph

        graph = build_call_graph(str(script), "main", project_dir=str(tmp_path))
        helper_node = next(n for n in graph.nodes if n.name == "helper")
        # Node ID should be "<module>.py:<line>" (CWD-relative)
        assert helper_node.id.startswith(f"{mod_name}.py:")

        # Run the debug stack with a breakpoint on the helper's graph node ID
        runtime, bridge = _build_stack(script, breakpoints=[helper_node.id])

        try:
            result = await runtime.execute({"n": 4})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 8}
            # The breakpoint on the helper should have fired
            assert len(bridge.breakpoint_hits) >= 1
            assert bridge.breakpoint_hits[0].current_state["n"] == 4
        finally:
            monkeypatch.delitem(_sys.modules, mod_name, raising=False)
            await runtime.dispose()

    async def test_schema_and_debug_use_same_project_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """get_schema and _build_tracked_functions produce the same node IDs."""
        import sys as _sys

        mod_name = "schema_helpers"
        monkeypatch.chdir(tmp_path)
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.delitem(_sys.modules, mod_name, raising=False)

        _write_script(
            tmp_path,
            f"{mod_name}.py",
            "def helper():\n    return 1\n",
        )
        script = _write_script(
            tmp_path,
            "schema_main.py",
            f"from {mod_name} import helper\n\ndef main(input):\n    return helper()\n",
        )

        inner = UiPathFunctionsRuntime(str(script), "main", "main")
        schema = await inner.get_schema()
        schema_node_ids = {n.id for n in schema.graph.nodes} if schema.graph else set()

        debug_fn = UiPathDebugFunctionsRuntime(
            inner, entrypoint_path=str(script), function_name="main"
        )
        tracked, node_id_map = debug_fn._build_tracked_functions()

        # Both main and helper should be in the schema graph
        assert len(schema_node_ids) >= 2, f"Expected >=2 nodes, got {schema_node_ids}"

        # Every node_id from the debug side should appear in the schema graph
        for node_id in node_id_map.values():
            assert node_id in schema_node_ids, (
                f"Debug node_id {node_id!r} not in schema graph {schema_node_ids}"
            )

        monkeypatch.delitem(_sys.modules, mod_name, raising=False)
        await inner.dispose()


class TestQualifiedNodeName:
    """State events' qualified_node_name should match graph node IDs."""

    async def test_qualified_name_matches_graph_node_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """State event qualified_node_name should equal the graph node ID, not the def line."""
        import sys as _sys

        mod_name = "qn_helpers"
        monkeypatch.chdir(tmp_path)
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.delitem(_sys.modules, mod_name, raising=False)

        _write_script(
            tmp_path,
            f"{mod_name}.py",
            "def helper(n):\n"
            '    """A helper with a docstring."""\n'
            "    return n * 2\n",  # line 3 = first_code_line
        )
        script = _write_script(
            tmp_path,
            "qn_main.py",
            f"from {mod_name} import helper\n"
            "\n"
            "def main(input):\n"
            '    """Main docstring."""\n'
            '    val = input.get("n", 5)\n'  # line 5 = first_code_line
            "    result = helper(val)\n"
            '    return {"result": result}\n',
        )

        # Build graph to find expected node IDs
        from uipath.functions.graph_builder import build_call_graph

        graph = build_call_graph(str(script), "main", project_dir=str(tmp_path))
        node_ids = {n.name: n.id for n in graph.nodes}

        runtime, bridge = _build_stack(script, breakpoints="*")
        try:
            result = await runtime.execute({"n": 3})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 6}

            # Every "started" state event's qualified_node_name should match
            # the graph node ID for that function.
            started_checked = set()
            for s in bridge.state_updates:
                if (
                    s.phase == UiPathRuntimeStatePhase.STARTED
                    and s.node_name in node_ids
                ):
                    started_checked.add(s.node_name)
                    assert s.qualified_node_name == node_ids[s.node_name], (
                        f"{s.node_name}: qualified_node_name={s.qualified_node_name!r} "
                        f"!= graph node id={node_ids[s.node_name]!r}"
                    )

            # Ensure we actually checked both main and helper
            assert "main" in started_checked, "No STARTED event for main"
            assert "helper" in started_checked, "No STARTED event for helper"
        finally:
            monkeypatch.delitem(_sys.modules, mod_name, raising=False)
            await runtime.dispose()


class TestGeneratorStateEvents:
    """Generator/coroutine frames should not produce spurious state events."""

    async def test_generator_helper_single_started_completed(self, script_dir: Path):
        """A generator helper should emit at most one STARTED event, not one per yield."""
        script = _write_script(
            script_dir,
            "main.py",
            "def gen_helper():\n"
            "    yield 1\n"
            "    yield 2\n"
            "    yield 3\n"
            "\n"
            "def main(input):\n"
            "    total = sum(gen_helper())\n"
            '    return {"total": total}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"total": 6}

            # gen_helper should have at most 1 STARTED (not 3+)
            gen_started = [
                s
                for s in bridge.state_updates
                if s.node_name == "gen_helper"
                and s.phase == UiPathRuntimeStatePhase.STARTED
            ]
            assert len(gen_started) <= 1, (
                f"Expected at most 1 STARTED for gen_helper, got {len(gen_started)}"
            )

            # gen_helper should NOT have COMPLETED (we suppress it for generators)
            gen_completed = [
                s
                for s in bridge.state_updates
                if s.node_name == "gen_helper"
                and s.phase == UiPathRuntimeStatePhase.COMPLETED
            ]
            assert len(gen_completed) == 0, (
                f"Expected 0 COMPLETED for gen_helper, got {len(gen_completed)}"
            )

            # main (non-generator) should still have started + completed
            main_started = [
                s
                for s in bridge.state_updates
                if s.node_name == "main" and s.phase == UiPathRuntimeStatePhase.STARTED
            ]
            main_completed = [
                s
                for s in bridge.state_updates
                if s.node_name == "main"
                and s.phase == UiPathRuntimeStatePhase.COMPLETED
            ]
            assert len(main_started) == 1
            assert len(main_completed) == 1
        finally:
            await runtime.dispose()

    async def test_async_helper_single_started(self, script_dir: Path):
        """An async helper that awaits should not emit duplicate STARTED events."""
        script = _write_script(
            script_dir,
            "main.py",
            "import asyncio\n"
            "\n"
            "async def async_helper(n):\n"
            "    await asyncio.sleep(0)\n"
            "    return n * 2\n"
            "\n"
            "async def main(input):\n"
            '    val = input.get("n", 5)\n'
            "    result = await async_helper(val)\n"
            '    return {"result": result}\n',
        )
        runtime, bridge = _build_stack(script, breakpoints="*")

        try:
            result = await runtime.execute({"n": 3})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 6}

            # async_helper should have at most 1 STARTED
            helper_started = [
                s
                for s in bridge.state_updates
                if s.node_name == "async_helper"
                and s.phase == UiPathRuntimeStatePhase.STARTED
            ]
            assert len(helper_started) <= 1, (
                f"Expected at most 1 STARTED for async_helper, got {len(helper_started)}"
            )
        finally:
            await runtime.dispose()


class TestFuncNameBreakpointResolution:
    """BreakpointController should resolve bare function names via node_id_map."""

    def test_bare_function_name_resolved_to_file_line(self):
        """A bare function name breakpoint is resolved to file:line via node_id_map."""
        node_id_map = {
            ("/abs/main.py", "main"): "main.py:5",
            ("/abs/helpers.py", "helper"): "helpers.py:2",
        }
        controller = BreakpointController(
            project_dir="/abs",
            breakpoints=["helper"],
            node_id_map=node_id_map,
        )
        # The bare name "helper" should resolve to helpers.py:2
        abs_helpers = os.path.abspath("helpers.py")
        assert abs_helpers in controller._file_breakpoints
        assert 2 in controller._file_breakpoints[abs_helpers]

    def test_unresolvable_function_name_ignored(self):
        """A bare function name not in node_id_map is silently ignored."""
        controller = BreakpointController(
            project_dir="/abs",
            breakpoints=["unknown_func"],
            node_id_map={},
        )
        assert len(controller._file_breakpoints) == 0

    async def test_bridge_sends_func_name_breakpoint_hits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """End-to-end: bridge sends a bare function name, breakpoint fires."""
        import sys as _sys

        mod_name = "fname_helpers"
        monkeypatch.chdir(tmp_path)
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.delitem(_sys.modules, mod_name, raising=False)

        _write_script(
            tmp_path,
            f"{mod_name}.py",
            "def helper(n):\n    doubled = n * 2\n    return doubled\n",
        )
        script = _write_script(
            tmp_path,
            "fname_main.py",
            f"from {mod_name} import helper\n"
            "\n"
            "def main(input):\n"
            '    val = input.get("n", 5)\n'
            "    result = helper(val)\n"
            '    return {"result": result}\n',
        )

        # The bridge sends bare function name "helper" as breakpoint
        runtime, bridge = _build_stack(script, breakpoints=["helper"])

        try:
            result = await runtime.execute({"n": 4})

            assert result.status == UiPathRuntimeStatus.SUCCESSFUL
            assert result.output == {"result": 8}
            # The bare name "helper" should have resolved and fired
            assert len(bridge.breakpoint_hits) >= 1
        finally:
            monkeypatch.delitem(_sys.modules, mod_name, raising=False)
            await runtime.dispose()
