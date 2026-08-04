"""Really stopping a job that is already executing.

``run``/``debug``/``eval`` each end in ``asyncio.run(...)`` on the worker thread, so a
job *is* an event loop. Capturing that loop turns cancellation from "impossible, the
thread is opaque" into an ordinary ``task.cancel()`` that unwinds the runtime
cooperatively — which is what these pin, using commands shaped like the real ones.
"""

import asyncio
import threading
import time
from typing import Any

import click
import pytest

from uipath._cli import _server_core
from uipath._cli._job_control import CURRENT_JOB_CONTROL, JobControl, run_job_loop
from uipath._cli._server_core import EXIT_CODE_STOPPED, _ServerState
from uipath._cli._server_jobs import JobRegistry


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(_server_core, "_state", _ServerState())


class FakeCallback:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.done = asyncio.Event()

    async def post_result(self, job_key: str, payload: dict[str, Any]) -> bool:
        self.results.append(payload)
        self.done.set()
        return True

    async def post_logs(self, job_key: str, lines: list[dict[str, Any]]) -> bool:
        return True


# Shaped like the real commands: a click command whose body is asyncio.run(...).
# Rebound per test by the _events fixture.
_started = threading.Event()
_cleanup_ran = threading.Event()


@click.command()
def _long_async_command() -> None:
    async def body() -> None:
        try:
            _started.set()
            await asyncio.sleep(30)
        finally:
            # Stands in for UiPathRuntimeContext.__exit__, which writes output.json.
            _cleanup_ran.set()

    run_job_loop(body())


@click.command()
def _quick_async_command() -> None:
    async def body() -> None:
        await asyncio.sleep(0)

    run_job_loop(body())


@click.command()
def _slow_cleanup_command() -> None:
    async def body() -> None:
        try:
            _started.set()
            await asyncio.sleep(30)
        finally:
            # The real cleanup awaits (flushing traces, closing clients), which is the
            # window a second cancellation would land in.
            await asyncio.sleep(0.5)
            _cleanup_ran.set()

    run_job_loop(body())


@click.command()
def _self_cancelling_command() -> None:
    async def body() -> None:
        _started.set()
        # Nobody asked this job to stop; its own code let a CancelledError escape.
        raise asyncio.CancelledError()

    run_job_loop(body())


@click.command()
def _blocking_command() -> None:
    # No event loop at all: models a job wedged in a non-cancellable C call.
    _started.set()
    time.sleep(30)


@pytest.fixture(autouse=True)
def _events():
    global _started, _cleanup_ran
    _started = threading.Event()
    _cleanup_ran = threading.Event()
    yield


async def _wait_for(event: threading.Event, timeout: float = 10.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not event.is_set():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("timed out waiting for the job to start")
        await asyncio.sleep(0.02)


# --------------------------------------------------------------------------- #
# the capture mechanism                                                       #
# --------------------------------------------------------------------------- #


def test_control_starts_unbound():
    control = JobControl("job-1")

    assert control.bound is False
    # Nothing to cancel yet, but the request must be remembered for bind().
    assert control.cancel() is False
    assert control.cancel_requested is True


def test_run_job_loop_is_plain_asyncio_run_outside_the_server():
    """`uipath run` on a terminal has no control in scope and must be unaffected."""
    assert CURRENT_JOB_CONTROL.get() is None

    async def body():
        return 42

    assert run_job_loop(body()) == 42


async def test_control_binds_to_the_loop_the_job_runs_on(tmp_path):
    _server_core._state.init()
    control = JobControl("job-1")

    await _server_core._run_command_isolated(
        _quick_async_command, [], {}, str(tmp_path), control=control
    )

    # Unbound again once the job finished.
    assert control.bound is False


async def test_a_stop_that_races_the_loop_is_still_applied(tmp_path):
    """A cancel arriving before the job builds its loop must not be dropped."""
    _server_core._state.init()
    control = JobControl("job-1")
    control.cancel()  # before anything is bound

    result = await _server_core._run_command_isolated(
        _long_async_command, [], {}, str(tmp_path), control=control
    )

    assert result["Stopped"] is True


# --------------------------------------------------------------------------- #
# stopping a running job for real                                             #
# --------------------------------------------------------------------------- #


async def test_stop_cancels_a_job_that_is_already_executing(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    registry.start("job-1", _long_async_command, [], {}, str(tmp_path), callback)
    await _wait_for(_started)

    stopped = await registry.stop("job-1")

    assert stopped is True, "a running job must actually stop, not just be refused"
    await asyncio.wait_for(callback.done.wait(), timeout=10)
    assert callback.results[0]["stopped"] is True
    assert callback.results[0]["exitCode"] == EXIT_CODE_STOPPED


async def test_cancel_delivers_a_single_cancellation_however_often_it_is_called():
    """A second delivery lands in the cleanup and aborts it, so cancel() absorbs it."""
    control = JobControl("job-1")
    loop = asyncio.get_running_loop()
    task = loop.create_task(asyncio.sleep(30))
    control.bind(loop, task)

    assert control.cancel() is True
    assert control.cancel() is True
    assert control.cancel() is True

    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelling() == 1


async def test_a_repeated_stop_does_not_abort_the_cleanup(tmp_path):
    """A stop followed by a force-stop escalation is ordinary; both must be honoured
    without the second one interrupting the cleanup that writes output.json."""
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    registry.start("job-1", _slow_cleanup_command, [], {}, str(tmp_path), callback)
    await _wait_for(_started)

    first, second = await asyncio.gather(registry.stop("job-1"), registry.stop("job-1"))

    assert (first, second) == (True, True)
    await asyncio.wait_for(callback.done.wait(), timeout=10)
    assert _cleanup_ran.is_set(), "the second stop interrupted the job's cleanup"
    assert callback.results[0]["stopped"] is True


async def test_a_self_inflicted_cancellation_is_a_fault_not_a_stop(tmp_path):
    """`cancelling() == 0` alone does not mean the caller asked for a stop — without a
    stop request a stray CancelledError is a job failure, and filing it as Stopped
    would report a fault as a clean stop."""
    _server_core._state.init()
    control = JobControl("job-1")

    result = await _server_core._run_command_isolated(
        _self_cancelling_command, [], {}, str(tmp_path), control=control
    )

    assert result.get("Stopped") is not True
    assert result["ExitCode"] != EXIT_CODE_STOPPED
    assert result["Unexpected"] is True


async def test_a_stopped_job_still_unwinds_its_cleanup(tmp_path):
    """Cooperative cancellation, not a thread kill: the runtime's context managers must
    still run, because that is what writes output.json for the caller to fall back on."""
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    registry.start("job-1", _long_async_command, [], {}, str(tmp_path), callback)
    await _wait_for(_started)

    await registry.stop("job-1")
    await asyncio.wait_for(callback.done.wait(), timeout=10)

    assert _cleanup_ran.is_set(), "the job's finally block must have run"


async def test_stop_releases_the_lock_for_the_next_job(tmp_path):
    """A stop that leaves the lock held would wedge the whole server."""
    _server_core._state.init()
    registry = JobRegistry()
    first = FakeCallback()
    second = FakeCallback()

    registry.start("job-1", _long_async_command, [], {}, str(tmp_path), first)
    await _wait_for(_started)
    await registry.stop("job-1")
    await asyncio.wait_for(first.done.wait(), timeout=10)

    registry.start("job-2", _quick_async_command, [], {}, str(tmp_path), second)
    await asyncio.wait_for(second.done.wait(), timeout=10)

    assert second.results[0]["exitCode"] == 0


async def test_a_normal_job_is_not_reported_stopped(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    registry.start("job-1", _quick_async_command, [], {}, str(tmp_path), callback)
    await asyncio.wait_for(callback.done.wait(), timeout=10)

    assert callback.results[0]["stopped"] is False
    assert callback.results[0]["exitCode"] == 0


async def test_stop_reports_failure_when_the_job_cannot_be_interrupted(
    tmp_path, monkeypatch
):
    """A job with no event loop — wedged in a C call — cannot be cancelled. Say so
    rather than claiming a stop that did not happen."""
    import uipath._cli._server_jobs as jobs

    monkeypatch.setattr(jobs, "STOP_GRACE_SECONDS", 1)
    monkeypatch.setattr(jobs, "STOP_ESCALATION_SECONDS", 1)

    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    registry.start("job-1", _blocking_command, [], {}, str(tmp_path), callback)
    await _wait_for(_started)

    assert await registry.stop("job-1") is False
