"""Async dispatch: enqueue, run, push the outcome back.

The contract is opt-in per request: a caller that supplies a result-callback socket
gets async dispatch, one that does not gets the original blocking call. These tests
pin both halves, because the blocking half is what every un-upgraded caller still uses.
"""

import asyncio
import json
import os
import time
from typing import Any, cast

import click
import pytest
from aiohttp import web

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
from uipath._cli.cli_server_ipc import StopJobRequest


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

    async def post_logs(self, job_key: str, lines: list[dict[str, Any]]) -> bool:
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
        "stopped": False,
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


async def test_stop_waits_for_a_running_job_to_finish(tmp_path, monkeypatch):
    """Stop no longer refuses a running job — it cancels and waits. A job that ends
    inside the grace window is a successful stop, whatever ended it."""
    import uipath._cli._server_jobs as jobs

    monkeypatch.setattr(jobs, "STOP_GRACE_SECONDS", 5)
    monkeypatch.setattr(jobs, "STOP_ESCALATION_SECONDS", 2)

    _server_core._state.init()
    registry = JobRegistry()
    callback = FakeCallback()
    started = asyncio.Event()

    @click.command()
    def _brief_command() -> None:
        started.set()
        time.sleep(0.3)

    registry.start("job-1", _brief_command, [], {}, str(tmp_path), callback)
    await asyncio.wait_for(started.wait(), timeout=10)

    assert await registry.stop("job-1") is True
    await asyncio.wait_for(callback.done.wait(), timeout=10)


async def test_stop_cancels_a_job_that_is_still_queued(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    first = FakeCallback()
    second = FakeCallback()
    started = asyncio.Event()
    release = asyncio.Event()

    @click.command()
    def _holds_the_lock() -> None:
        started.set()
        waited = 0
        while not release.is_set() and waited < 200:
            time.sleep(0.02)
            waited += 1

    registry.start("job-1", _holds_the_lock, [], {}, str(tmp_path), first)
    await asyncio.wait_for(started.wait(), timeout=10)

    # job-2 is queued behind the lock, so it has not started executing.
    registry.start("job-2", _ok_command, [], {}, str(tmp_path), second)
    cancelled = await registry.stop("job-2")

    release.set()
    await asyncio.wait_for(first.done.wait(), timeout=10)

    assert cancelled is True


# --------------------------------------------------------------------------- #
# HTTP dispatch                                                               #
# --------------------------------------------------------------------------- #


class _FakeRequest:
    def __init__(self, job_key: str, payload: dict[str, Any]) -> None:
        self.match_info = {"job_key": job_key}
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload


def _fake_request(job_key: str, payload: dict[str, Any]) -> web.Request:
    """handle_start only touches match_info and json(); the cast keeps mypy honest."""
    return cast(web.Request, _FakeRequest(job_key, payload))


def _body(response: web.Response) -> dict[str, Any]:
    assert response.text is not None
    return cast("dict[str, Any]", json.loads(response.text))


class _RecordingRegistry:
    def __init__(self, accept: bool = True) -> None:
        self.accept = accept
        self.started: list[str] = []
        self.resume_versions: list[int | None] = []

    def start(
        self, job_key, cmd, args, env_vars, working_dir, callback, resume_version=None
    ):
        self.started.append(job_key)
        self.resume_versions.append(resume_version)
        return self.accept


async def test_http_start_with_callback_returns_accepted(monkeypatch):
    registry = _RecordingRegistry()
    monkeypatch.setattr(cli_server, "get_registry", lambda: registry)

    response = await cli_server.handle_start(
        _fake_request(
            "job-1",
            {"command": "run", "resultCallbackSocket": "/tmp/ack.sock"},
        )
    )

    assert response.status == 202
    body = _body(response)
    assert body["disposition"] == "accepted"
    assert body["contractVersion"] == CONTRACT_VERSION
    assert registry.started == ["job-1"]


async def test_http_start_duplicate_is_409(monkeypatch):
    monkeypatch.setattr(
        cli_server, "get_registry", lambda: _RecordingRegistry(accept=False)
    )

    response = await cli_server.handle_start(
        _fake_request(
            "job-1", {"command": "run", "resultCallbackSocket": "/tmp/ack.sock"}
        )
    )

    assert response.status == 409
    assert _body(response)["success"] is False


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

    response = await cli_server.handle_start(_fake_request("job-1", {"command": "run"}))

    assert called.get("ran") is True
    assert response.status == 200
    body = _body(response)
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
    assert "already in flight" in (result.Error or "")


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


async def test_stop_ignores_a_command_for_a_previous_resume_version(tmp_path):
    """A suspended job resumes under the SAME key. A stop raised against run N that
    arrives after N+1 started must not kill N+1."""
    _server_core._state.init()
    registry = JobRegistry()
    first = FakeCallback()
    started = asyncio.Event()
    release = asyncio.Event()

    @click.command()
    def _holds_the_lock() -> None:
        started.set()
        waited = 0
        while not release.is_set() and waited < 200:
            time.sleep(0.02)
            waited += 1

    registry.start(
        "job-1", _holds_the_lock, [], {}, str(tmp_path), first, resume_version=2
    )
    await asyncio.wait_for(started.wait(), timeout=10)

    # A stop for the run that was suspended before this one.
    assert await registry.stop("job-1", resume_version=1) is False

    release.set()
    await asyncio.wait_for(first.done.wait(), timeout=10)

    assert first.results[0]["exitCode"] == 0


async def test_stop_applies_to_the_matching_resume_version(tmp_path):
    _server_core._state.init()
    registry = JobRegistry()
    first = FakeCallback()
    second = FakeCallback()
    started = asyncio.Event()
    release = asyncio.Event()

    @click.command()
    def _holds_the_lock() -> None:
        started.set()
        waited = 0
        while not release.is_set() and waited < 200:
            time.sleep(0.02)
            waited += 1

    registry.start("job-1", _holds_the_lock, [], {}, str(tmp_path), first)
    await asyncio.wait_for(started.wait(), timeout=10)

    registry.start(
        "job-2", _ok_command, [], {}, str(tmp_path), second, resume_version=3
    )
    assert await registry.stop("job-2", resume_version=3) is True

    release.set()
    await asyncio.wait_for(first.done.wait(), timeout=10)


# --------------------------------------------------------------------------- #
# HTTP stop — the transport production actually uses                          #
# --------------------------------------------------------------------------- #


class _RecordingStopRegistry:
    def __init__(self, stopped: bool = True) -> None:
        self.stopped = stopped
        self.calls: list[tuple[str, int | None]] = []

    async def stop(self, job_key, resume_version=None):
        self.calls.append((job_key, resume_version))
        return self.stopped


async def test_http_stop_reaches_the_registry(monkeypatch):
    """Stop was previously unreachable over HTTP, which is the transport carrying all
    production traffic — an operator stop simply never reached the runtime."""
    registry = _RecordingStopRegistry()
    monkeypatch.setattr(cli_server, "get_registry", lambda: registry)

    response = await cli_server.handle_stop(_FakeRequest("job-1", {}))

    assert response.status == 200
    body = json.loads(response.text)
    assert body["stopped"] is True
    assert registry.calls == [("job-1", None)]


async def test_http_stop_forwards_the_resume_version(monkeypatch):
    registry = _RecordingStopRegistry()
    monkeypatch.setattr(cli_server, "get_registry", lambda: registry)

    await cli_server.handle_stop(_FakeRequest("job-1", {"resumeVersion": 2}))

    assert registry.calls == [("job-1", 2)]


async def test_http_stop_reports_a_refused_stop(monkeypatch):
    """A job wedged in a non-cancellable call must be reported honestly, not as stopped."""
    monkeypatch.setattr(
        cli_server, "get_registry", lambda: _RecordingStopRegistry(stopped=False)
    )

    response = await cli_server.handle_stop(_FakeRequest("job-1", {}))

    assert response.status == 200
    assert json.loads(response.text)["stopped"] is False


async def test_ipc_stop_forwards_the_dto_fields(monkeypatch):
    """The .NET peer sends a StopJobRequest; both identity fields must reach the registry
    or the resume-version guard is inert."""
    registry = _RecordingStopRegistry()
    monkeypatch.setattr(cli_server_ipc, "get_registry", lambda: registry)

    await cli_server_ipc.PythonRuntimeService().StopJob(
        StopJobRequest(JobKey="job-1", ResumeVersion=2, ForceStop=True)
    )

    assert registry.calls == [("job-1", 2)]
