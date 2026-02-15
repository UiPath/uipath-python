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
from uipath.runtime import (
    UiPathBreakpointResult,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath.runtime.debug import UiPathDebugRuntime
from uipath.runtime.events import UiPathRuntimeStateEvent

from uipath.functions.debug import BreakpointController, UiPathDebugFunctionsRuntime
from uipath.functions.runtime import UiPathFunctionsRuntime


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
            # Only main — json.dumps is external
            assert state_names == ["main"]
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

            helper_states = [s for s in bridge.state_updates if s.node_name == "helper"]
            assert len(helper_states) == 1
            # At call time, x and y should be in the payload
            assert helper_states[0].payload["x"] == 1
            assert helper_states[0].payload["y"] == 2
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
