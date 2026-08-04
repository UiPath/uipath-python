"""The callback URLs and payload keys the .NET handler parses.

The handler declares these routes as its own string constants
(``Constants.PythonRuntimeContract`` in GenericExecutors.PythonCoded, pinned by
``PythonRuntimeContractRoutesTests``). Nothing at build time ties the two sides together,
so a rename on either side is a 404 on every push — which this side treats as retryable,
leaving the job to never complete. These assertions make such a rename a deliberate,
visible change with a failing test on both sides.
"""

from typing import Any

import pytest

from uipath._cli._server_jobs import (
    CONTRACT_VERSION,
    HandlerCallback,
    build_result_payload,
)


class _CapturingCallback(HandlerCallback):
    """Captures what would be POSTed instead of opening a socket."""

    def __init__(self) -> None:
        super().__init__("/tmp/never-connected.sock")
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.response = True

    async def _post(self, path: str, payload: dict[str, Any]):
        from uipath._cli._server_jobs import _PostOutcome

        self.posts.append((path, payload))
        return _PostOutcome.DELIVERED if self.response else _PostOutcome.UNREACHABLE


async def test_result_is_posted_to_the_route_the_handler_serves():
    callback = _CapturingCallback()

    await callback.post_result("abc-123", {"exitCode": 0})

    path, _ = callback.posts[0]
    assert path == "/api/python/jobs/abc-123/result"


async def test_logs_are_posted_to_the_route_the_handler_serves():
    callback = _CapturingCallback()

    await callback.post_logs("abc-123", [{"message": "hello"}])

    path, _ = callback.posts[0]
    assert path == "/api/python/jobs/abc-123/logs"


async def test_log_payload_carries_the_keys_the_handler_deserializes():
    """RuntimeJobLogsDto maps contractVersion / jobKey / lines[].{timestamp,level,message}."""
    callback = _CapturingCallback()

    await callback.post_logs(
        "abc-123",
        [{"timestamp": "2026-07-29 17:00:00,000", "level": "INFO", "message": "hi"}],
    )

    _, payload = callback.posts[0]
    assert payload["contractVersion"] == CONTRACT_VERSION
    assert payload["jobKey"] == "abc-123"
    assert payload["lines"] == [
        {"timestamp": "2026-07-29 17:00:00,000", "level": "INFO", "message": "hi"}
    ]


def test_result_payload_carries_the_keys_the_handler_deserializes():
    """RuntimeJobResultDto maps exactly these camelCase keys."""
    payload = build_result_payload("abc-123", {"ExitCode": 0, "Document": "{}"})

    assert set(payload) == {
        "contractVersion",
        "jobKey",
        "exitCode",
        "error",
        "unexpected",
        "stateConveyance",
        "jobConveyance",
        "job",
        "stopped",
    }


async def test_result_push_retries_until_it_lands():
    """A briefly unavailable callback socket must not strand the job."""
    callback = _CapturingCallback()
    callback.response = False

    attempts: list[int] = []

    from uipath._cli._server_jobs import _PostOutcome

    async def _flaky(path: str, payload: dict[str, Any]) -> _PostOutcome:
        attempts.append(1)
        return (
            _PostOutcome.DELIVERED if len(attempts) >= 3 else _PostOutcome.UNREACHABLE
        )

    callback._post = _flaky  # type: ignore[method-assign]

    # Collapse the backoff so the test does not actually wait minutes.
    import uipath._cli._server_jobs as jobs

    original = jobs.RESULT_PUSH_BACKOFF_SECONDS
    jobs.RESULT_PUSH_BACKOFF_SECONDS = 0.0
    try:
        assert await callback.post_result("abc-123", {"exitCode": 0}) is True
    finally:
        jobs.RESULT_PUSH_BACKOFF_SECONDS = original

    assert len(attempts) == 3


async def test_result_push_eventually_gives_up_without_raising():
    """Giving up must be a warning, not an exception: this runs in a background task and
    ConsoleLogger.error is NoReturn (it calls ctx.exit)."""
    callback = _CapturingCallback()
    callback.response = False

    import uipath._cli._server_jobs as jobs

    original_backoff = jobs.RESULT_PUSH_BACKOFF_SECONDS
    original_attempts = jobs.RESULT_PUSH_ATTEMPTS
    jobs.RESULT_PUSH_BACKOFF_SECONDS = 0.0
    jobs.RESULT_PUSH_ATTEMPTS = 3
    try:
        result = await callback.post_result("abc-123", {"exitCode": 0})
    finally:
        jobs.RESULT_PUSH_BACKOFF_SECONDS = original_backoff
        jobs.RESULT_PUSH_ATTEMPTS = original_attempts

    assert result is False
    assert len(callback.posts) == 3


async def test_undeliverable_result_asks_the_server_to_stop(tmp_path):
    """If the callback socket is unreachable, no job we hold can ever be reported and
    StartJob no longer blocks — so every one of them would hang. Exiting hands them to
    the caller's service-exit path, which completes them from their result files."""
    import click

    from uipath._cli import _server_core
    from uipath._cli._server_jobs import JobRegistry, shutdown_event

    @click.command()
    def _ok() -> None:
        return None

    class _DeadCallback(HandlerCallback):
        def __init__(self) -> None:
            super().__init__("/tmp/unreachable.sock")
            self.done = __import__("asyncio").Event()

        async def post_result(self, job_key, payload):
            self.done.set()
            return False

        async def post_logs(self, job_key, lines):
            return False

    import asyncio

    _server_core._state.init()
    assert not shutdown_event().is_set()

    callback = _DeadCallback()
    JobRegistry().start("job-1", _ok, [], {}, str(tmp_path), callback)
    await asyncio.wait_for(callback.done.wait(), timeout=10)
    await asyncio.sleep(0)

    assert shutdown_event().is_set()


async def test_a_delivered_result_does_not_stop_the_server(tmp_path):
    import asyncio

    import click

    from uipath._cli import _server_core
    from uipath._cli._server_jobs import JobRegistry, shutdown_event

    @click.command()
    def _ok() -> None:
        return None

    class _LiveCallback(HandlerCallback):
        def __init__(self) -> None:
            super().__init__("/tmp/live.sock")
            self.done = asyncio.Event()

        async def post_result(self, job_key, payload):
            self.done.set()
            return True

        async def post_logs(self, job_key, lines):
            return True

    _server_core._state.init()
    callback = _LiveCallback()
    JobRegistry().start("job-1", _ok, [], {}, str(tmp_path), callback)
    await asyncio.wait_for(callback.done.wait(), timeout=10)
    await asyncio.sleep(0)

    assert not shutdown_event().is_set()


async def test_logs_are_not_retried():
    """A dropped log batch must never delay the job."""
    callback = _CapturingCallback()
    callback.response = False

    assert await callback.post_logs("abc-123", [{"message": "x"}]) is False
    assert len(callback.posts) == 1


@pytest.mark.parametrize("job_key", ["abc-123", "00000000-0000-0000-0000-000000000000"])
async def test_route_is_built_from_the_job_key_verbatim(job_key):
    callback = _CapturingCallback()

    await callback.post_result(job_key, {})

    assert callback.posts[0][0] == f"/api/python/jobs/{job_key}/result"
