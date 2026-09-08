"""The uipath-python job-api glue: result mapping and the runtime-sink installer.

The runtime side (``uipath.runtime.output_sinks``) is faked here so these tests exercise the wiring
in isolation — that install points a log handler + result sink at the callback, that the handler
forwards SendLog, and that the result sink maps the runtime result and calls SetResult.
"""

import asyncio
import logging
import os
import sys
import threading
import types
from typing import Any

import pytest

from uipath._cli import _job_api


def test_to_result_dto_maps_status_error_and_path():
    class _Category:
        value = "User"

    class _Error:
        code = "BOOM"
        title = "It broke"
        detail = "stack"
        category = _Category()
        status = None

    class _Result:
        status = "faulted"
        error = _Error()

    dto = _job_api._to_result_dto("job-1", _Result(), "out.args")

    assert dto.id == "job-1"
    assert dto.status == _job_api.ExecutorJobStatus.FAULTED.value
    assert dto.outputArgumentsFilePath == "out.args"
    assert dto.outputArguments is None
    assert dto.error is not None
    assert (dto.error.Code, dto.error.Category) == ("BOOM", "User")


def test_to_result_dto_defaults_to_successful_without_error():
    class _Result:
        status = "successful"
        error = None

    dto = _job_api._to_result_dto("j", _Result(), "p.args")
    assert dto.status == _job_api.ExecutorJobStatus.SUCCESSFUL.value
    assert dto.error is None


def test_to_log_level_maps_python_levels_to_wire_values():
    assert _job_api._to_log_level(logging.CRITICAL) == _job_api.LogLevel.CRITICAL
    assert _job_api._to_log_level(logging.ERROR) == _job_api.LogLevel.ERROR
    assert _job_api._to_log_level(logging.WARNING) == _job_api.LogLevel.WARNING
    assert _job_api._to_log_level(logging.INFO) == _job_api.LogLevel.INFORMATION
    assert _job_api._to_log_level(logging.DEBUG) == _job_api.LogLevel.DEBUG
    assert _job_api._to_log_level(logging.NOTSET) == _job_api.LogLevel.TRACE
    # A level between two named severities rounds down to the lower one.
    assert _job_api._to_log_level(logging.WARNING + 5) == _job_api.LogLevel.WARNING


def test_dto_wire_key_sets_are_pinned():
    """Pin each DTO's on-wire JSON keys so an accidental rename is caught on this side.

    Guards our half of the wire contract: JobResultDto is camelCase, JobLogDto / JobExecutorError
    are PascalCase.
    """
    serialization = pytest.importorskip("uipath_ipc.wire.serialization")
    to_wire = serialization.to_wire

    result_keys = set(
        to_wire(_job_api.JobResultDto(id="j", outputArgumentsFilePath="p.args"))
    )
    assert result_keys == {
        "id",
        "status",
        "outputArguments",
        "outputArgumentsFilePath",
        "info",
        "error",
    }
    assert set(to_wire(_job_api.JobLogDto(Message="m"))) == {"Message", "LogLevel"}
    assert set(to_wire(_job_api.JobExecutorError(Code="c"))) == {
        "Code",
        "Title",
        "Detail",
        "Category",
        "Status",
    }


def _fake_output_sinks(monkeypatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    module = types.ModuleType("uipath.runtime.output_sinks")
    module.set_log_handler = lambda h: captured.__setitem__("handler", h)  # type: ignore[attr-defined]
    module.set_result_sink = lambda s: captured.__setitem__("sink", s)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uipath.runtime.output_sinks", module)
    return captured


def test_install_wires_log_handler_and_result_sink(monkeypatch):
    captured = _fake_output_sinks(monkeypatch)
    logs: list[tuple[str, Any]] = []
    results: list[tuple[str, Any]] = []

    class _Callback:
        async def SendLog(self, jid: str, dto: Any) -> None:
            logs.append((jid, dto))

        async def SetResult(self, jid: str, dto: Any) -> bool:
            results.append((jid, dto))
            return True

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        _job_api.install_runtime_sinks("job-7", _Callback(), loop)

        # The log handler forwards each record as SendLog, tagged with the job id.
        handler = captured["handler"]
        handler.emit(
            logging.LogRecord("n", logging.WARNING, "p", 1, "hi %s", ("there",), None)
        )
        await asyncio.sleep(0.05)
        assert logs[0][0] == "job-7"
        assert logs[0][1].Message == "hi there"
        assert logs[0][1].LogLevel == _job_api.LogLevel.WARNING.value

        # The result sink maps the result and calls SetResult, off a worker thread, for the ack.
        class _Result:
            status = "successful"
            error = None

        sink = captured["sink"]
        await asyncio.to_thread(sink, _Result(), "out.args")
        assert results[0][0] == "job-7"
        assert results[0][1].outputArgumentsFilePath == "out.args"

    asyncio.run(scenario())


def test_install_is_a_noop_without_the_runtime(monkeypatch):
    # An older uipath-runtime has no output_sinks module: install/clear must not raise.
    monkeypatch.setitem(sys.modules, "uipath.runtime.output_sinks", None)
    _job_api.install_runtime_sinks("j", object(), asyncio.new_event_loop())
    _job_api.clear_runtime_sinks()


def test_connect_installs_sinks_and_disconnect_clears(monkeypatch):
    pytest.importorskip("uipath_ipc")
    captured = _fake_output_sinks(monkeypatch)

    async def scenario() -> None:
        # A named-pipe client connects lazily, so no server is needed to build it.
        client = _job_api.connect_handler_ipc("some-pipe", "job-1")
        assert captured["handler"] is not None
        assert captured["sink"] is not None

        await _job_api.disconnect_handler_ipc(client)
        assert captured["handler"] is None
        assert captured["sink"] is None

    asyncio.run(scenario())


def test_connect_without_uipath_ipc_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "uipath_ipc", None)
    with pytest.raises(RuntimeError, match="uipath-ipc"):
        _job_api.connect_handler_ipc("pipe", "job-1")


_jobapi_pipe_counter = 0


def _unique_jobapi_pipe() -> str:
    global _jobapi_pipe_counter
    _jobapi_pipe_counter += 1
    return f"uipath-jobapi-test-{os.getpid()}-{_jobapi_pipe_counter}"


def _serve_jobapi_in_background(pipe: str, api: Any):
    """Host ``api`` as IJobInvocationCommonApi on ``pipe`` in a daemon thread; return a stop() callable.

    The server runs on its OWN loop/thread so it can keep accepting while the test thread is
    blocked inside the (synchronous) result sink — the whole point of the regression below.
    """
    from uipath_ipc import IpcServer, NamedPipeServerTransport

    loop = asyncio.new_event_loop()
    ready = threading.Event()
    holder: dict[str, Any] = {}

    async def _serve() -> None:
        server = IpcServer(
            transport=NamedPipeServerTransport(pipe),
            services={_job_api.IJobInvocationCommonApi: api},
            request_timeout=None,
        )
        holder["server"] = server
        async with server:  # __aenter__ binds the listener
            ready.set()
            await server.serve_forever()

    def _run() -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_serve())
        except Exception:
            pass
        finally:
            loop.close()

    thread = threading.Thread(target=_run, name="jobapi-test-server", daemon=True)
    thread.start()
    if not ready.wait(timeout=10):
        raise TimeoutError(f"job-api test server on {pipe!r} did not start")

    def stop() -> None:
        server = holder.get("server")
        if server is not None:
            try:
                asyncio.run_coroutine_threadsafe(server.aclose(), loop).result(
                    timeout=10
                )
            except Exception:
                pass
        thread.join(timeout=10)

    return stop


def test_result_sink_delivers_when_invoked_on_the_caller_loop_thread(monkeypatch):
    """Regression for the non-pooled deadlock.

    Under ``uipath run`` the runtime invokes the result sink synchronously on the job's own asyncio
    loop thread, and the sink blocks for the handler's ack. If that ack were scheduled onto the same
    loop it could never run — 30s timeout, dropped result. ``connect_handler_ipc`` isolates the
    connection on its own loop, so the ack still completes. Here we drive the real sink on the
    caller's loop thread against a real in-proc server and assert SetResult actually arrived.
    """
    pytest.importorskip("uipath_ipc")
    captured = _fake_output_sinks(monkeypatch)
    received: dict[str, Any] = {}

    class _Api(_job_api.IJobInvocationCommonApi):
        async def SendLog(self, jobId: str, log: Any) -> None:
            received.setdefault("logs", []).append((jobId, log))

        async def SetResult(self, jobId: str, result: Any) -> bool:
            # The server deserializes against the contract's typed signature, so result arrives as a
            # real JobResultDto (this also exercises the wire round-trip of the DTO).
            received["result"] = (jobId, result)
            return True

    class _Result:
        status = "successful"
        error = None

    pipe = _unique_jobapi_pipe()
    stop = _serve_jobapi_in_background(pipe, _Api())
    try:

        async def scenario() -> None:
            conn = _job_api.connect_handler_ipc(pipe, "job-77")
            # Call the sink ON this loop's thread, exactly as the runtime's __exit__ does. Before the
            # fix this deadlocked the loop the ack was scheduled on; now it completes.
            captured["sink"](_Result(), "out.args")
            await _job_api.disconnect_handler_ipc(conn)

        asyncio.run(scenario())
    finally:
        stop()

    assert "result" in received, (
        "SetResult never arrived — the result sink deadlocked/timed out"
    )
    job_id, dto = received["result"]
    assert job_id == "job-77"
    assert dto.outputArgumentsFilePath == "out.args"
    assert dto.status == _job_api.ExecutorJobStatus.SUCCESSFUL.value
