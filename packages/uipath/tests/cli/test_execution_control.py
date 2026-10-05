"""What an execution's loop tells the runtime about the stops it delivers."""

import contextvars
import sys
import types
from typing import Any

import pytest

from uipath._cli._execution_control import (
    CURRENT_EXECUTION_CONTROL,
    ExecutionControl,
    run_execution_loop,
)


def _run_controlled(control: ExecutionControl, coro: Any) -> Any:
    token = CURRENT_EXECUTION_CONTROL.set(control)
    try:
        return run_execution_loop(coro)
    finally:
        CURRENT_EXECUTION_CONTROL.reset(token)


@pytest.fixture
def stop_module(monkeypatch: pytest.MonkeyPatch) -> contextvars.ContextVar[Any]:
    probe: contextvars.ContextVar[Any] = contextvars.ContextVar("probe", default=None)
    module = types.ModuleType("uipath.runtime.stop")
    module.set_stop_requested_probe = probe.set  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uipath.runtime.stop", module)
    return probe


def test_the_runtime_learns_the_execution_was_asked_to_stop(
    stop_module: contextvars.ContextVar[Any],
) -> None:
    control = ExecutionControl()

    async def body() -> tuple[bool, bool]:
        probe = stop_module.get()
        before = probe()
        control.cancel_requested = True
        return before, probe()

    assert _run_controlled(control, body()) == (False, True)


def test_the_probe_stays_inside_the_execution(
    stop_module: contextvars.ContextVar[Any],
) -> None:
    async def body() -> None:
        return None

    _run_controlled(ExecutionControl(), body())

    assert stop_module.get() is None


def test_an_uncontrolled_run_installs_no_probe(
    stop_module: contextvars.ContextVar[Any],
) -> None:
    async def body() -> Any:
        return stop_module.get()

    assert run_execution_loop(body()) is None


def test_a_runtime_without_the_probe_still_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "uipath.runtime.stop", None)

    async def body() -> str:
        return "ran"

    assert _run_controlled(ExecutionControl(), body()) == "ran"
