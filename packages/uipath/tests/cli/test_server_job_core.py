"""Unit tests for ``_run_command_isolated`` — the shared job core behind both the
HTTP and uipath-ipc channels. These drive its error branches directly (bad
working dir, SystemExit, unexpected exception, uninitialized state) without
standing up a transport, so they run fast on every OS/Python.
"""

import asyncio
import os
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


# The pooled channel installs a per-job sink via on_run_start and clears it via
# on_run_end. The IPC layer's own tests fake this core, so the placement guarantees
# below (clear-on-raise, install-after-cwd, no hooks on the bad-cwd early return)
# are pinned here against the real core.


@pytest.mark.parametrize("boom", [SystemExit(2), ValueError("kaboom")])
async def test_on_run_end_fires_even_when_the_job_raises(
    restore_state: Any, boom: BaseException
) -> None:
    _init(restore_state)
    events: list[str] = []
    cmd = Mock()
    cmd.main.side_effect = boom
    await _server_core._run_command_isolated(
        cmd,
        [],
        {},
        None,
        on_run_start=lambda: events.append("start"),
        on_run_end=lambda: events.append("end"),
    )
    # on_run_end is in a finally, so a raising job still clears its sink before the
    # next job runs — otherwise a stale sink would cross-wire the next job.
    assert events == ["start", "end"]


async def test_on_run_start_sees_the_jobs_cwd_and_env(
    restore_state: Any, tmp_path: Any
) -> None:
    _init(restore_state)
    seen: dict[str, Any] = {}
    cmd = Mock()

    def _start() -> None:
        seen["cwd"] = os.getcwd()
        seen["env"] = os.environ.get("JOB_VAR")

    await _server_core._run_command_isolated(
        cmd,
        [],
        {"JOB_VAR": "42"},
        str(tmp_path),
        on_run_start=_start,
        on_run_end=lambda: None,
    )
    # The hook runs after env/cwd are applied, so it sees exactly what the job sees.
    assert os.path.samefile(seen["cwd"], str(tmp_path))
    assert seen["env"] == "42"


async def test_hooks_do_not_run_on_bad_working_dir(
    restore_state: Any, tmp_path: Any
) -> None:
    _init(restore_state)
    events: list[str] = []
    result = await _server_core._run_command_isolated(
        Mock(),
        [],
        {},
        str(tmp_path / "does-not-exist"),
        on_run_start=lambda: events.append("start"),
        on_run_end=lambda: events.append("end"),
    )
    assert result["ClientError"] is True
    # The early return sits above on_run_start: no install means no clear owed.
    assert events == []


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
