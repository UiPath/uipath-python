"""Async dispatch: enqueue, run, push the outcome back.

The contract is opt-in per request: a caller that supplies a result-callback socket
gets async dispatch, one that does not gets the original blocking call. These tests
pin both halves, because the blocking half is what every un-upgraded caller still uses.
"""

import asyncio
import json
import os
from typing import Any

import click
import pytest

from uipath._cli import _server_core, cli_server, cli_server_ipc
from uipath._cli._server_core import (
    MAX_INLINE_DOCUMENT_BYTES,
    _read_result_document,
    _ServerState,
    resolve_result_file_path,
)
from uipath._cli._server_jobs import (
    CONTRACT_VERSION,
    JobRegistry,
    build_result_payload,
)


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(_server_core, "_state", _ServerState())


class FakeCallback:
    """Records result pushes instead of posting them."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.done = asyncio.Event()

    async def post_result(self, job_key: str, payload: dict[str, Any]) -> bool:
        self.results.append(payload)
        self.done.set()
        return True


def _write_config(tmp_path, runtime: dict[str, Any] | None) -> str:
    config = {"runtime": runtime} if runtime is not None else {}
    path = tmp_path / "uipath.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------- #
# result document resolution                                                  #
# --------------------------------------------------------------------------- #


def test_resolve_result_file_path_uses_runtime_config(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "UIPATH_CONFIG_PATH",
        _write_config(
            tmp_path, {"dir": str(tmp_path / "__uipath"), "outputFile": "output.json"}
        ),
    )

    resolved = resolve_result_file_path()

    assert resolved == os.path.abspath(str(tmp_path / "__uipath" / "output.json"))


def test_resolve_result_file_path_defaults_when_runtime_block_absent(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UIPATH_CONFIG_PATH", _write_config(tmp_path, None))

    resolved = resolve_result_file_path()

    assert resolved == os.path.abspath(os.path.join("__uipath", "output.json"))


def test_resolve_result_file_path_falls_back_to_defaults_when_config_missing(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UIPATH_CONFIG_PATH", str(tmp_path / "nope.json"))

    resolved = resolve_result_file_path()

    assert resolved == os.path.abspath(os.path.join("__uipath", "output.json"))


def test_read_result_document_inline(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "__uipath"
    runtime_dir.mkdir()
    (runtime_dir / "output.json").write_text(
        '{"status":"successful"}', encoding="utf-8"
    )
    monkeypatch.setenv(
        "UIPATH_CONFIG_PATH",
        _write_config(tmp_path, {"dir": str(runtime_dir), "outputFile": "output.json"}),
    )

    document, conveyance = _read_result_document()

    assert conveyance == "inline"
    assert document == '{"status":"successful"}'


def test_read_result_document_falls_back_to_file_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "UIPATH_CONFIG_PATH",
        _write_config(
            tmp_path, {"dir": str(tmp_path / "__uipath"), "outputFile": "output.json"}
        ),
    )

    document, conveyance = _read_result_document()

    assert (document, conveyance) == (None, "file")


def test_read_result_document_falls_back_to_file_when_oversized(tmp_path, monkeypatch):
    """Large outputs already work via the file; they must not start failing on the wire."""
    runtime_dir = tmp_path / "__uipath"
    runtime_dir.mkdir()
    (runtime_dir / "output.json").write_text(
        "x" * (MAX_INLINE_DOCUMENT_BYTES + 1), encoding="utf-8"
    )
    monkeypatch.setenv(
        "UIPATH_CONFIG_PATH",
        _write_config(tmp_path, {"dir": str(runtime_dir), "outputFile": "output.json"}),
    )

    document, conveyance = _read_result_document()

    assert (document, conveyance) == (None, "file")


# --------------------------------------------------------------------------- #
# payload shape                                                               #
# --------------------------------------------------------------------------- #


def test_build_result_payload_shape():
    payload = build_result_payload(
        "job-1",
        {
            "ExitCode": 0,
            "Error": None,
            "Unexpected": False,
            "Document": '{"status":"successful"}',
            "DocumentConveyance": "inline",
        },
    )

    assert payload == {
        "contractVersion": CONTRACT_VERSION,
        "jobKey": "job-1",
        "exitCode": 0,
        "error": None,
        "unexpected": False,
        "stateConveyance": "file",
        "jobConveyance": "inline",
        "job": '{"status":"successful"}',
    }


def test_build_result_payload_defaults_to_failure_when_outcome_is_bare():
    payload = build_result_payload("job-1", {})

    assert payload["exitCode"] == 1
    assert payload["jobConveyance"] == "file"
    assert payload["job"] is None


# --------------------------------------------------------------------------- #
# registry                                                                    #
# --------------------------------------------------------------------------- #


@click.command()
def _ok_command() -> None:
    return None


@click.command()
def _failing_command() -> None:
    click.get_current_context().exit(3)


async def test_registry_runs_job_and_pushes_result(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    assert registry.start("job-1", _ok_command, [], {}, str(tmp_path), callback)

    await asyncio.wait_for(callback.done.wait(), timeout=10)

    assert len(callback.results) == 1
    assert callback.results[0]["jobKey"] == "job-1"
    assert callback.results[0]["exitCode"] == 0


async def test_registry_pushes_failure_exit_code(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    registry.start("job-1", _failing_command, [], {}, str(tmp_path), callback)
    await asyncio.wait_for(callback.done.wait(), timeout=10)

    assert callback.results[0]["exitCode"] == 3


async def test_registry_rejects_a_duplicate_job_key(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    assert registry.start("job-1", _ok_command, [], {}, str(tmp_path), callback) is True
    # Second start while the first is in flight must not silently replace it.
    second = registry.start("job-1", _ok_command, [], {}, str(tmp_path), callback)

    await asyncio.wait_for(callback.done.wait(), timeout=10)
    assert second is False


async def test_registry_frees_the_key_after_completion(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()

    registry.start("job-1", _ok_command, [], {}, str(tmp_path), callback)
    await asyncio.wait_for(callback.done.wait(), timeout=10)
    await asyncio.sleep(0)  # let the done-callback run

    assert registry.is_active("job-1") is False


async def test_stop_is_true_for_an_unknown_job():
    registry = JobRegistry()

    assert await registry.stop("never-seen") is True


# --------------------------------------------------------------------------- #
# HTTP dispatch                                                               #
# --------------------------------------------------------------------------- #


class _FakeRequest:
    def __init__(self, job_key: str, payload: dict[str, Any]) -> None:
        self.match_info = {"job_key": job_key}
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload


class _RecordingRegistry:
    def __init__(self, accept: bool = True) -> None:
        self.accept = accept
        self.started: list[str] = []

    def start(self, job_key, cmd, args, env_vars, working_dir, callback):
        self.started.append(job_key)
        return self.accept


async def test_http_start_with_callback_returns_accepted(monkeypatch):
    registry = _RecordingRegistry()
    monkeypatch.setattr(cli_server, "get_registry", lambda: registry)

    response = await cli_server.handle_start(
        _FakeRequest(
            "job-1",
            {"command": "run", "resultCallbackSocket": "/tmp/ack.sock"},
        )
    )

    assert response.status == 202
    body = json.loads(response.text)
    assert body["disposition"] == "accepted"
    assert body["contractVersion"] == CONTRACT_VERSION
    assert registry.started == ["job-1"]


async def test_http_start_duplicate_is_409(monkeypatch):
    monkeypatch.setattr(
        cli_server, "get_registry", lambda: _RecordingRegistry(accept=False)
    )

    response = await cli_server.handle_start(
        _FakeRequest(
            "job-1", {"command": "run", "resultCallbackSocket": "/tmp/ack.sock"}
        )
    )

    assert response.status == 409
    assert json.loads(response.text)["success"] is False


async def test_http_start_without_callback_stays_synchronous(monkeypatch):
    """An un-upgraded caller must get the original blocking behaviour, byte for byte."""
    called: dict[str, Any] = {}

    async def _fake_isolated(cmd, args, env_vars, working_dir):
        called["ran"] = True
        return {"ExitCode": 0, "Error": None, "Result": {"out": 1}, "Unexpected": False}

    monkeypatch.setattr(cli_server, "_run_command_isolated", _fake_isolated)
    monkeypatch.setattr(
        cli_server,
        "get_registry",
        lambda: pytest.fail("registry must not be used without a callback socket"),
    )

    response = await cli_server.handle_start(_FakeRequest("job-1", {"command": "run"}))

    assert called.get("ran") is True
    assert response.status == 200
    body = json.loads(response.text)
    assert body["success"] is True
    assert "disposition" not in body


# --------------------------------------------------------------------------- #
# IPC dispatch                                                                #
# --------------------------------------------------------------------------- #


async def test_ipc_start_with_callback_returns_accepted(monkeypatch):
    registry = _RecordingRegistry()
    monkeypatch.setattr(cli_server_ipc, "get_registry", lambda: registry)

    result = await cli_server_ipc.PythonRuntimeService().RunJob(
        cli_server_ipc.RunJobRequest(
            JobKey="job-1", Command="run", ResultCallbackSocket="/tmp/ack.sock"
        )
    )

    assert result.Disposition == "accepted"
    assert result.ExitCode == 0
    assert result.ContractVersion == CONTRACT_VERSION
    assert registry.started == ["job-1"]


async def test_ipc_start_duplicate_reports_failure(monkeypatch):
    monkeypatch.setattr(
        cli_server_ipc, "get_registry", lambda: _RecordingRegistry(accept=False)
    )

    result = await cli_server_ipc.PythonRuntimeService().RunJob(
        cli_server_ipc.RunJobRequest(
            JobKey="job-1", Command="run", ResultCallbackSocket="/tmp/ack.sock"
        )
    )

    assert result.ExitCode == 1
    assert result.Disposition is None
    assert "already in flight" in result.Error


async def test_ipc_start_without_callback_stays_synchronous(monkeypatch):
    async def _fake_isolated(cmd, args, env_vars, working_dir):
        return {
            "ExitCode": 7,
            "Error": "Exit code: 7",
            "Result": None,
            "Unexpected": False,
        }

    monkeypatch.setattr(cli_server_ipc, "_run_command_isolated", _fake_isolated)

    result = await cli_server_ipc.PythonRuntimeService().RunJob(
        cli_server_ipc.RunJobRequest(JobKey="job-1", Command="run")
    )

    assert result.ExitCode == 7
    assert result.Disposition is None
