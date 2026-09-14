"""The uipath-python job-api glue: result mapping and the runtime-sink installer.

The runtime side (``uipath.runtime.output_sinks``) is faked here so these tests exercise the wiring
in isolation — that install points a log handler + result sink at the callback, that the handler
forwards SendLog, and that the result sink maps the runtime result and calls SetResult.
"""

import asyncio
import io
import logging
import os
import sys
import threading
import types
from typing import Any

import pytest

from uipath._cli import _job_api
from uipath.runtime.result import UiPathRuntimeStatus

JOB_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
JOB_ID_2 = "9a7b1c22-0e54-4f7d-8c31-6b2f0a5d9e10"


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
        status = UiPathRuntimeStatus.FAULTED
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
        status = UiPathRuntimeStatus.SUCCESSFUL
        error = None

    dto = _job_api._to_result_dto("j", _Result(), "p.args")
    assert dto.status == _job_api.ExecutorJobStatus.SUCCESSFUL.value
    assert dto.error is None


def test_to_result_dto_maps_suspended():
    class _Result:
        status = UiPathRuntimeStatus.SUSPENDED
        error = None

    dto = _job_api._to_result_dto("j", _Result(), "p.args")
    assert dto.status == _job_api.ExecutorJobStatus.SUSPENDED.value


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
            status = UiPathRuntimeStatus.SUCCESSFUL
            error = None

        sink = captured["sink"]
        await asyncio.to_thread(sink, _Result(), "out.args")
        assert results[0][0] == "job-7"
        assert results[0][1].outputArgumentsFilePath == "out.args"

    asyncio.run(scenario())


def test_log_forwarding_failure_does_not_escape_emit(monkeypatch):
    captured = _fake_output_sinks(monkeypatch)

    class _Callback:
        def SendLog(self, jid: str, dto: Any) -> None:
            raise RuntimeError("pipe is gone")

    loop = asyncio.new_event_loop()
    try:
        _job_api.install_runtime_sinks("job-8", _Callback(), loop)
        handler = captured["handler"]
        handled: list[Any] = []
        monkeypatch.setattr(handler, "handleError", handled.append)
        handler.emit(logging.LogRecord("n", logging.INFO, "p", 1, "hi", (), None))
        assert len(handled) == 1
    finally:
        loop.close()


def test_transport_and_self_logs_never_ride_the_ipc_channel(monkeypatch):
    captured = _fake_output_sinks(monkeypatch)
    sent: list[Any] = []
    forwarded = threading.Event()

    class _Callback:
        async def SendLog(self, jid: str, dto: Any) -> None:
            sent.append((jid, dto))
            forwarded.set()

    buf = io.StringIO()
    monkeypatch.setattr(sys, "__stderr__", buf)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        _job_api.install_runtime_sinks("job-6", _Callback(), loop)
        handler = captured["handler"]
        for name in ("uipath_ipc.client.connection", _job_api.__name__):
            handler.emit(
                logging.LogRecord(
                    name, logging.WARNING, "p", 1, "internal chatter", (), None
                )
            )
        handler.emit(
            logging.LogRecord("job.logger", logging.INFO, "p", 1, "job line", (), None)
        )
        forwarded.wait(timeout=5)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()

    assert [dto.Message for _, dto in sent] == ["job line"]
    assert buf.getvalue().count("internal chatter") == 2


def test_rejected_result_is_reported(monkeypatch):
    captured = _fake_output_sinks(monkeypatch)

    class _Callback:
        async def SetResult(self, jid: str, dto: Any) -> bool:
            return False

    class _Result:
        status = UiPathRuntimeStatus.SUCCESSFUL
        error = None

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    api_logger = logging.getLogger("uipath._cli._job_api")
    handler = _Capture()
    api_logger.addHandler(handler)
    prior_level = api_logger.level
    api_logger.setLevel(logging.ERROR)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        _job_api.install_runtime_sinks("job-8", _Callback(), loop)
        captured["sink"](_Result(), "out.args")
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()
        api_logger.removeHandler(handler)
        api_logger.setLevel(prior_level)

    assert any("rejected" in r.getMessage().lower() for r in records)


def test_teardown_does_not_raise_when_the_loop_thread_is_wedged():
    loop = asyncio.new_event_loop()
    started = threading.Event()
    release = threading.Event()

    def _run() -> None:
        asyncio.set_event_loop(loop)

        async def _block() -> None:
            started.set()
            release.wait(timeout=10)

        loop.run_until_complete(_block())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    assert started.wait(timeout=5)

    _job_api._stop_loop_thread(loop, thread, 0.2)
    assert thread.is_alive()

    release.set()
    thread.join(timeout=5)
    loop.close()


def test_pending_log_sends_are_flushed_before_teardown(monkeypatch):
    _fake_output_sinks(monkeypatch)
    landed: list[str] = []

    class _Callback:
        async def SendLog(self, jid: str, dto: Any) -> None:
            await asyncio.sleep(0.2)
            landed.append(dto.Message)

    class _Client:
        async def aclose(self) -> None:
            return None

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    handler = _job_api.install_runtime_sinks("job-7", _Callback(), loop)
    assert handler is not None
    handler.emit(logging.LogRecord("j", logging.INFO, "p", 1, "tail line", (), None))

    conn = _job_api._HandlerIpcConnection(_Client(), loop, thread, handler)
    conn._shutdown()

    assert landed == ["tail line"]


def test_result_delivery_failure_is_swallowed_and_logged(monkeypatch):
    captured = _fake_output_sinks(monkeypatch)

    class _Callback:
        async def SetResult(self, jid: str, dto: Any) -> bool:
            raise RuntimeError("handler said no")

    class _Result:
        status = UiPathRuntimeStatus.SUCCESSFUL
        error = None

    # Capture on the module logger directly, not via caplog: other tests in the suite mutate root
    # handlers / propagate, which would silently drop the record from caplog.
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    api_logger = logging.getLogger("uipath._cli._job_api")
    handler = _Capture()
    api_logger.addHandler(handler)
    prior_level = api_logger.level
    api_logger.setLevel(logging.ERROR)

    # Ack loop on its own thread so the cross-thread wait is deterministic.
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        _job_api.install_runtime_sinks("job-9", _Callback(), loop)
        sink = captured["sink"]
        sink(_Result(), "out.args")  # must not raise
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()
        api_logger.removeHandler(handler)
        api_logger.setLevel(prior_level)

    assert any(
        "Failed to deliver job result over IPC" in r.getMessage() for r in records
    )


def test_install_is_a_noop_without_the_runtime(monkeypatch):
    # An older uipath-runtime has no output_sinks module: install/clear must not raise.
    monkeypatch.setitem(sys.modules, "uipath.runtime.output_sinks", None)
    _job_api.install_runtime_sinks("j", object(), asyncio.new_event_loop())
    _job_api.clear_runtime_sinks()


def test_connect_installs_sinks_and_disconnect_clears(monkeypatch):
    pytest.importorskip("uipath_ipc")
    captured = _fake_output_sinks(monkeypatch)

    class _Api(_job_api.IJobInvocationCommonApi):
        async def SendLog(self, jobId: str, log: Any) -> None:
            return None

        async def SetResult(self, jobId: str, result: Any) -> bool:
            return True

    pipe = _unique_jobapi_pipe()
    stop = _serve_jobapi_in_background(pipe, _Api())
    try:

        async def scenario() -> None:
            conn = _job_api.connect_handler_ipc(pipe, JOB_ID)
            assert captured["handler"] is not None
            assert captured["sink"] is not None

            await _job_api.disconnect_handler_ipc(conn)
            assert captured["handler"] is None
            assert captured["sink"] is None

        asyncio.run(scenario())
    finally:
        stop()


def test_connect_fails_loudly_when_the_pipe_is_unreachable(monkeypatch):
    pytest.importorskip("uipath_ipc")
    _fake_output_sinks(monkeypatch)

    def live() -> int:
        return len(
            [
                t
                for t in threading.enumerate()
                if t.name == "uipath-handler-ipc" and t.is_alive()
            ]
        )

    before = live()

    with pytest.raises(RuntimeError, match="Could not reach the handler IPC pipe"):
        _job_api.connect_handler_ipc("uipath-jobapi-does-not-exist-12345", JOB_ID)

    assert live() == before


def test_connect_without_uipath_ipc_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "uipath_ipc", None)
    with pytest.raises(RuntimeError, match="uipath-ipc"):
        _job_api.connect_handler_ipc("pipe", JOB_ID)


def _live_ipc_threads() -> int:
    return len(
        [
            t
            for t in threading.enumerate()
            if t.name == "uipath-handler-ipc" and t.is_alive()
        ]
    )


@pytest.mark.parametrize("job_id", [None, "", " ", "job-1", "not-a-guid"])
def test_connect_without_a_real_job_id_fails_fast(job_id):
    before = _live_ipc_threads()
    with pytest.raises(RuntimeError, match="UIPATH_JOB_KEY"):
        _job_api.connect_handler_ipc("pipe", job_id)
    assert _live_ipc_threads() == before


@pytest.mark.parametrize("job_id", [None, "", "job-1"])
async def test_handler_ipc_connection_without_a_real_job_id_fails_fast(job_id):
    with pytest.raises(RuntimeError, match="UIPATH_JOB_KEY"):
        async with _job_api.handler_ipc_connection("pipe", job_id):
            pass


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
        status = UiPathRuntimeStatus.SUCCESSFUL
        error = None

    pipe = _unique_jobapi_pipe()
    stop = _serve_jobapi_in_background(pipe, _Api())
    try:

        async def scenario() -> None:
            conn = _job_api.connect_handler_ipc(pipe, JOB_ID_2)
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
    assert job_id == JOB_ID_2
    assert dto.outputArgumentsFilePath == "out.args"
    assert dto.status == _job_api.ExecutorJobStatus.SUCCESSFUL.value
