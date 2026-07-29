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
