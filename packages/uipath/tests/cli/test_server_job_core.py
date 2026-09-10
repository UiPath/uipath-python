"""Unit tests for ``_run_command_isolated`` — the shared job core behind both the
HTTP and uipath-ipc channels. These drive its error branches directly (bad
working dir, SystemExit, unexpected exception, uninitialized state) without
standing up a transport, so they run fast on every OS/Python.
"""

import asyncio
import logging
import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import Mock

import pytest

from uipath._cli import _server_core


@pytest.fixture
def restore_state():
    """Save/restore the module-level _ServerState singleton around a test."""
    saved_lock = _server_core._state.lock
    saved_env = _server_core._state.baseline_env
    try:
        yield _server_core._state
    finally:
        _server_core._state.lock = saved_lock
        _server_core._state.baseline_env = saved_env


def _init(state: Any) -> None:
    state.lock = asyncio.Lock()
    state.baseline_env = dict(os.environ)


async def test_requires_initialized_state(restore_state: Any) -> None:
    restore_state.lock = None
    restore_state.baseline_env = None
    cmd = Mock()
    with pytest.raises(RuntimeError, match="not initialized"):
        await _server_core._run_command_isolated(cmd, [], {}, None)


async def test_rejects_bad_working_dir(restore_state: Any, tmp_path: Any) -> None:
    _init(restore_state)
    missing = str(tmp_path / "does-not-exist")
    result = await _server_core._run_command_isolated(Mock(), [], {}, missing)
    assert result["ExitCode"] == 1
    assert "working directory" in result["Error"]
    assert result["Unexpected"] is False
    assert result["ClientError"] is True  # HTTP maps this to 400


async def test_maps_system_exit_code(restore_state: Any) -> None:
    _init(restore_state)
    cmd = Mock()
    cmd.main.side_effect = SystemExit(2)
    result = await _server_core._run_command_isolated(cmd, [], {}, None)
    assert result["ExitCode"] == 2
    assert result["Unexpected"] is False


async def test_reports_unexpected_exception(restore_state: Any) -> None:
    _init(restore_state)
    cmd = Mock()
    cmd.main.side_effect = ValueError("boom")
    result = await _server_core._run_command_isolated(cmd, [], {}, None)
    assert result["ExitCode"] == 1
    assert result["Unexpected"] is True
    assert "boom" in result["Error"]


# parse_args accepts what every caller sends: the .NET peer sends a single
# string (shlex-split), HTTP dicts / tests may send a pre-split list, or None.


def test_parse_args_splits_a_string() -> None:
    # The real .NET-shaped Args: a single string, shlex-split into argv.
    assert _server_core.parse_args("run --input-file in.json --flag") == [
        "run",
        "--input-file",
        "in.json",
        "--flag",
    ]


def test_parse_args_passes_a_list_through() -> None:
    assert _server_core.parse_args(["run", "--input-file", "in.json"]) == [
        "run",
        "--input-file",
        "in.json",
    ]


def test_parse_args_none_is_empty() -> None:
    assert _server_core.parse_args(None) == []


# ---------------------------------------------------------------------------
# Per-job scope hook (register_job_scope_provider)
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the test with no provider registered; restore the original afterwards.

    ``monkeypatch`` records the original value, so it is put back even when the
    test registers a provider through :func:`register_job_scope_provider`.
    """
    monkeypatch.setattr(_server_core, "_job_scope_provider", None)


@pytest.fixture
def capture_core_logs(
    caplog: pytest.LogCaptureFixture,
) -> Iterator[pytest.LogCaptureFixture]:
    """Attach caplog's handler directly to this module's logger.

    Earlier tests in the suite invoke the Click CLI, whose ``setup_logging``
    leaves the ``uipath`` logger with ``propagate = False``, so records never
    reach the root handler caplog normally relies on.
    """
    logger = logging.getLogger(_server_core.__name__)
    level, propagate = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = True
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)
        logger.setLevel(level)
        logger.propagate = propagate


def _scope_recorder(events: list[tuple[str, str | None, str]]) -> Any:
    """A provider whose scope records entry/exit plus the env and cwd it observed."""

    @asynccontextmanager
    async def provider() -> Any:
        events.append(("enter", os.environ.get("JOB_MARKER"), os.getcwd()))
        try:
            yield
        finally:
            events.append(("exit", os.environ.get("JOB_MARKER"), os.getcwd()))

    return provider


async def test_no_provider_registered_runs_the_job_unchanged(
    restore_state: Any, restore_provider: Any
) -> None:
    _init(restore_state)
    cmd = Mock()
    cmd.main.return_value = "ok"
    result = await _server_core._run_command_isolated(cmd, [], {}, None)
    assert result == {
        "ExitCode": 0,
        "Error": None,
        "Result": "ok",
        "Unexpected": False,
    }


async def test_scope_sees_the_jobs_env_and_cwd(
    restore_state: Any, restore_provider: Any, tmp_path: Any
) -> None:
    """The whole point of the hook: it is entered after env/cwd are applied.

    A caller that had to wrap this function from outside would see neither, which is why the
    scope belongs inside.
    """
    _init(restore_state)
    events: list[tuple[str, str | None, str]] = []
    _server_core.register_job_scope_provider(_scope_recorder(events))

    cmd = Mock()
    cmd.main.return_value = "ok"
    await _server_core._run_command_isolated(
        cmd, [], {"JOB_MARKER": "job-1"}, str(tmp_path)
    )

    assert [e[0] for e in events] == ["enter", "exit"]
    assert {e[1] for e in events} == {"job-1"}  # the job's env, not the baseline
    assert all(
        os.path.realpath(e[2]) == os.path.realpath(str(tmp_path)) for e in events
    )
    # ...and the server's own state is restored afterwards.
    assert "JOB_MARKER" not in os.environ


async def test_scope_exits_before_the_job_env_is_restored(
    restore_state: Any, restore_provider: Any
) -> None:
    """Teardown inside the scope can still read the job's environment."""
    _init(restore_state)
    seen: list[str | None] = []

    @asynccontextmanager
    async def provider() -> Any:
        try:
            yield
        finally:
            seen.append(os.environ.get("JOB_MARKER"))

    _server_core.register_job_scope_provider(provider)
    cmd = Mock()
    cmd.main.return_value = "ok"
    await _server_core._run_command_isolated(cmd, [], {"JOB_MARKER": "job-1"}, None)

    assert seen == ["job-1"]


async def test_scope_wraps_the_command(
    restore_state: Any, restore_provider: Any
) -> None:
    """Ordering: enter -> command -> exit."""
    _init(restore_state)
    order: list[str] = []

    @asynccontextmanager
    async def provider() -> Any:
        order.append("enter")
        try:
            yield
        finally:
            order.append("exit")

    _server_core.register_job_scope_provider(provider)

    def record_command(*args: Any, **kwargs: Any) -> str:
        order.append("command")
        return "ok"

    cmd = Mock()
    cmd.main.side_effect = record_command
    await _server_core._run_command_isolated(cmd, [], {}, None)

    assert order == ["enter", "command", "exit"]


async def test_scope_exits_when_the_command_raises(
    restore_state: Any, restore_provider: Any
) -> None:
    """The scope must be exited on the job's failure path too."""
    _init(restore_state)
    order: list[str] = []

    @asynccontextmanager
    async def provider() -> Any:
        order.append("enter")
        try:
            yield
        finally:
            order.append("exit")

    _server_core.register_job_scope_provider(provider)
    cmd = Mock()
    cmd.main.side_effect = RuntimeError("boom")
    result = await _server_core._run_command_isolated(cmd, [], {}, None)

    assert order == ["enter", "exit"]
    assert result["ExitCode"] == 1
    assert result["Unexpected"] is True


async def test_a_provider_that_fails_to_start_does_not_fail_the_job(
    restore_state: Any, restore_provider: Any, capture_core_logs: Any
) -> None:
    """Best-effort by contract: a broken provider means no scope, not a failed job."""
    _init(restore_state)

    def provider() -> Any:
        raise RuntimeError("provider is broken")

    _server_core.register_job_scope_provider(provider)
    cmd = Mock()
    cmd.main.return_value = "ok"
    result = await _server_core._run_command_isolated(cmd, [], {}, None)

    assert result["ExitCode"] == 0
    assert result["Result"] == "ok"
    assert "job runs unscoped" in capture_core_logs.text


async def test_a_provider_that_fails_to_exit_does_not_change_the_result(
    restore_state: Any, restore_provider: Any, capture_core_logs: Any
) -> None:
    _init(restore_state)

    @asynccontextmanager
    async def provider() -> Any:
        yield
        raise RuntimeError("exit is broken")

    _server_core.register_job_scope_provider(provider)
    cmd = Mock()
    cmd.main.return_value = "ok"
    result = await _server_core._run_command_isolated(cmd, [], {}, None)

    assert result["ExitCode"] == 0
    assert result["Result"] == "ok"
    assert "failed to exit" in capture_core_logs.text


async def test_registering_none_removes_the_scope(
    restore_state: Any, restore_provider: Any
) -> None:
    _init(restore_state)
    events: list[tuple[str, str | None, str]] = []
    _server_core.register_job_scope_provider(_scope_recorder(events))
    _server_core.register_job_scope_provider(None)

    cmd = Mock()
    cmd.main.return_value = "ok"
    await _server_core._run_command_isolated(cmd, [], {}, None)

    assert events == []


async def test_scope_teardown_survives_cancellation(
    restore_state: Any, restore_provider: Any
) -> None:
    """A cancel arriving during teardown must not leave the provider half torn down."""
    _init(restore_state)
    teardown_started = asyncio.Event()
    release_teardown = asyncio.Event()
    teardown_finished = asyncio.Event()

    @asynccontextmanager
    async def provider() -> Any:
        try:
            yield
        finally:
            teardown_started.set()
            await release_teardown.wait()
            teardown_finished.set()

    _server_core.register_job_scope_provider(provider)
    cmd = Mock()
    cmd.main.return_value = "ok"

    task = asyncio.create_task(_server_core._run_command_isolated(cmd, [], {}, None))
    await asyncio.wait_for(teardown_started.wait(), timeout=5)
    task.cancel()
    release_teardown.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(teardown_finished.wait(), timeout=5)
