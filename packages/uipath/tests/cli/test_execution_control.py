"""What an execution's loop tells the runtime about the stops it delivers."""

import asyncio
from typing import Any

from uipath._cli._execution_control import (
    CURRENT_EXECUTION_CONTROL,
    ExecutionControl,
    run_execution_loop,
)
from uipath.runtime.stop import get_stop_requested_probe


def _run_controlled(control: ExecutionControl, coro: Any) -> Any:
    token = CURRENT_EXECUTION_CONTROL.set(control)
    try:
        return run_execution_loop(coro)
    finally:
        CURRENT_EXECUTION_CONTROL.reset(token)


def test_the_runtime_learns_a_stop_reached_the_execution() -> None:
    control = ExecutionControl()

    async def body() -> tuple[bool, bool]:
        probe = get_stop_requested_probe()
        assert probe is not None
        before = probe()
        control.cancel()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            return before, probe()
        return before, False

    assert _run_controlled(control, body()) == (False, True)


def test_a_stop_that_reaches_a_finished_execution_is_not_delivered() -> None:
    control = ExecutionControl()
    loop = asyncio.new_event_loop()
    try:
        task = loop.create_task(asyncio.sleep(0))
        loop.run_until_complete(task)
        control.bind(loop, task)
        control.cancel()
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        loop.close()

    assert control.cancel_requested is True
    assert control.delivered is False


def test_the_probe_stays_inside_the_execution() -> None:
    async def body() -> None:
        return None

    _run_controlled(ExecutionControl(), body())

    assert get_stop_requested_probe() is None


def test_an_uncontrolled_run_installs_no_probe() -> None:
    async def body() -> Any:
        return get_stop_requested_probe()

    assert run_execution_loop(body()) is None
