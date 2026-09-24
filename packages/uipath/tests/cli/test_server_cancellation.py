"""Stopping a job that ``uipath server`` is running.

The commands below are shaped like run/debug/eval: a click command whose body ends in
``run_job_loop(...)`` on the worker thread.
"""

import asyncio
import os
import threading
import time
from typing import Any

import click
import pytest
from aiohttp.test_utils import TestClient, TestServer

from uipath._cli import _server_core, cli_server, cli_server_ipc
from uipath._cli._job_control import CURRENT_JOB_CONTROL, run_job_loop
from uipath._cli._server_core import (
    EXIT_CODE_STOPPED,
    _run_command_isolated,
    _ServerState,
    stop_job,
)

JOB = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
OTHER_JOB = "5b1f6c9e-2d4a-4e8b-9f3c-7a6d5e4c3b2a"

started = threading.Event()
cleanup_ran = threading.Event()
release = threading.Event()


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch: pytest.MonkeyPatch) -> _ServerState:
    state = _ServerState()
    state.lock = asyncio.Lock()
    state.baseline_env = dict(os.environ)
    monkeypatch.setattr(_server_core, "_state", state)
    monkeypatch.setattr(cli_server_ipc, "_state", state)
    started.clear()
    cleanup_ran.clear()
    release.clear()
    return state


@pytest.fixture
def short_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "STOP_GRACE_SECONDS",
        "STOP_ESCALATION_SECONDS",
        "FORCE_STOP_GRACE_SECONDS",
        "FORCE_STOP_ESCALATION_SECONDS",
    ):
        monkeypatch.setattr(_server_core, name, 0.2)


@click.command()
def long_job() -> None:
    async def body() -> None:
        try:
            started.set()
            await asyncio.sleep(30)
        finally:
            cleanup_ran.set()

    run_job_loop(body())


@click.command()
def slow_cleanup_job() -> None:
    async def body() -> None:
        try:
            started.set()
            await asyncio.sleep(30)
        finally:
            await asyncio.sleep(0.3)
            cleanup_ran.set()

    run_job_loop(body())


@click.command()
def late_loop_job() -> None:
    started.set()
    release.wait(10)

    async def body() -> None:
        try:
            await asyncio.sleep(30)
        finally:
            cleanup_ran.set()

    run_job_loop(body())


@click.command()
def nested_thread_job() -> None:
    async def body() -> None:
        started.set()
        await asyncio.to_thread(time.sleep, 0.5)

    run_job_loop(body())


@click.command()
def self_cancelling_job() -> None:
    async def body() -> None:
        started.set()
        raise asyncio.CancelledError()

    run_job_loop(body())


@click.command()
def blocking_job() -> None:
    started.set()
    release.wait(10)


@click.command()
def quick_job() -> None:
    async def body() -> None:
        await asyncio.sleep(0)

    run_job_loop(body())


async def wait_until(event: threading.Event, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not event.is_set():
        assert time.monotonic() < deadline, "timed out"
        await asyncio.sleep(0.01)


def start(cmd: Any, job_key: str = JOB, **kwargs: Any) -> "asyncio.Task[Any]":
    return asyncio.create_task(
        _run_command_isolated(cmd, [], {}, None, job_key=job_key, **kwargs)
    )


def test_run_job_loop_is_asyncio_run_outside_the_server() -> None:
    assert CURRENT_JOB_CONTROL.get() is None

    async def body() -> int:
        return 42

    assert run_job_loop(body()) == 42


async def test_stop_unwinds_a_running_job_and_frees_the_lock(
    fresh_state: _ServerState,
) -> None:
    job = start(long_job)
    await wait_until(started)

    assert await stop_job(JOB) is True
    outcome = await job

    assert outcome["ExitCode"] == EXIT_CODE_STOPPED
    assert outcome["Stopped"] is True
    assert cleanup_ran.is_set()
    assert fresh_state.lock is not None and not fresh_state.lock.locked()
    assert fresh_state.jobs == []


async def test_a_stop_before_the_job_has_a_loop_is_applied_when_it_gets_one() -> None:
    job = start(late_loop_job)
    await wait_until(started)

    stopping = asyncio.create_task(stop_job(JOB))
    await asyncio.sleep(0.05)
    release.set()

    assert await stopping is True
    assert (await job)["ExitCode"] == EXIT_CODE_STOPPED
    assert cleanup_ran.is_set()


async def test_a_repeated_stop_does_not_abort_the_cleanup() -> None:
    job = start(slow_cleanup_job)
    await wait_until(started)

    first = asyncio.create_task(stop_job(JOB))
    await asyncio.sleep(0.05)
    second = asyncio.create_task(stop_job(JOB, force=True))

    assert await first is True
    assert await second is True
    assert (await job)["ExitCode"] == EXIT_CODE_STOPPED
    assert cleanup_ran.is_set()


async def test_a_job_waiting_on_its_own_thread_stops_once_that_call_returns() -> None:
    job = start(nested_thread_job)
    await wait_until(started)

    assert await stop_job(JOB) is True
    assert (await job)["ExitCode"] == EXIT_CODE_STOPPED


async def test_an_uninterruptible_job_reports_false_and_keeps_the_lock(
    fresh_state: _ServerState, short_waits: None
) -> None:
    job = start(blocking_job)
    await wait_until(started)

    assert await stop_job(JOB) is False
    assert fresh_state.lock is not None and fresh_state.lock.locked()
    assert not job.done()

    release.set()
    outcome = await job
    assert outcome["ExitCode"] == 0
    assert not fresh_state.lock.locked()


async def test_a_self_inflicted_cancellation_is_a_fault_not_a_stop() -> None:
    outcome = await start(self_cancelling_job)

    assert outcome["ExitCode"] == 1
    assert outcome["Unexpected"] is True
    assert "Stopped" not in outcome


async def test_a_queued_job_is_stopped_without_running(
    fresh_state: _ServerState,
) -> None:
    running = start(long_job)
    await wait_until(started)
    queued = start(quick_job, job_key=OTHER_JOB)
    await asyncio.sleep(0.05)

    assert await stop_job(OTHER_JOB) is True
    assert (await queued)["ExitCode"] == EXIT_CODE_STOPPED
    assert not running.done()

    assert await stop_job(JOB) is True
    await running
    assert fresh_state.jobs == []


async def test_a_stop_for_another_resume_version_leaves_the_live_run_alone() -> None:
    job = start(long_job, resume_version=2)
    await wait_until(started)

    assert await stop_job(JOB, resume_version=1) is True
    await asyncio.sleep(0.05)
    assert not job.done()
    assert not cleanup_ran.is_set()

    assert await stop_job(JOB, resume_version=2) is True
    assert (await job)["ExitCode"] == EXIT_CODE_STOPPED


async def test_stopping_an_unknown_job_reports_it_is_not_running() -> None:
    assert await stop_job("no-such-job") is True


async def test_a_cancelled_caller_stops_the_job_and_waits_for_its_thread(
    fresh_state: _ServerState,
) -> None:
    job = asyncio.create_task(
        _run_command_isolated(
            slow_cleanup_job, [], {"JOB_MARKER": "job-1"}, None, job_key=JOB
        )
    )
    await wait_until(started)

    job.cancel()
    with pytest.raises(asyncio.CancelledError):
        await job

    assert cleanup_ran.is_set()
    assert fresh_state.lock is not None and not fresh_state.lock.locked()
    assert os.environ.get("JOB_MARKER") is None


async def test_a_cancelled_caller_keeps_the_lock_while_the_thread_runs(
    fresh_state: _ServerState,
) -> None:
    job = asyncio.create_task(
        _run_command_isolated(
            blocking_job, [], {"JOB_MARKER": "job-1"}, None, job_key=JOB
        )
    )
    await wait_until(started)

    job.cancel()
    await asyncio.sleep(0.1)
    assert not job.done()
    assert fresh_state.lock is not None and fresh_state.lock.locked()
    assert os.environ.get("JOB_MARKER") == "job-1"

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await job
    assert not fresh_state.lock.locked()
    assert os.environ.get("JOB_MARKER") is None


async def test_ipc_stop_job_stops_a_running_run_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(_server_core.COMMANDS, "long", long_job)
    service = cli_server_ipc.PythonRuntimeService()
    run = asyncio.create_task(
        service.RunJob(
            cli_server_ipc.PythonServerRunRequest(
                jobKey=JOB, resumeVersion=3, command="long"
            )
        )
    )
    await wait_until(started)

    stopped = await service.StopJob(
        cli_server_ipc.PythonServerStopJobRequest(jobKey=JOB, resumeVersion=3)
    )

    assert stopped is True
    result = await run
    assert result.exitCode == EXIT_CODE_STOPPED
    assert result.error == "Job stopped on request"


async def test_http_stop_route_stops_a_running_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(_server_core.COMMANDS, "long", long_job)
    async with TestClient(TestServer(cli_server.create_app())) as client:
        start_request = asyncio.create_task(
            client.post(f"/jobs/{JOB}/start", json={"command": "long"})
        )
        await wait_until(started)

        stop = await client.post(f"/jobs/{JOB}/stop", json={"forceStop": True})
        assert stop.status == 200
        assert (await stop.json())["stopped"] is True

        response = await start_request
        body = await response.json()
        assert body["success"] is False
        assert body["exitCode"] == EXIT_CODE_STOPPED


async def test_http_stop_route_accepts_an_empty_body() -> None:
    async with TestClient(TestServer(cli_server.create_app())) as client:
        response = await client.post(f"/jobs/{JOB}/stop")
        assert response.status == 200
        assert (await response.json())["stopped"] is True


async def test_http_stop_route_rejects_a_bad_resume_version() -> None:
    async with TestClient(TestServer(cli_server.create_app())) as client:
        response = await client.post(f"/jobs/{JOB}/stop", json={"resumeVersion": "two"})
        assert response.status == 400
