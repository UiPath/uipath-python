"""The uipath-python job-api glue: result mapping and the runtime-sink installer.

The runtime's real ``output_sinks`` ContextVars are used, with a fresh pair per test: a dict would
record that a sink was installed but not in which context, and the context is the thing that decides
whether the job ever sees it.
"""

import asyncio
import io
import logging
import os
import sys
import threading
import time
from concurrent.futures import Future
from contextvars import ContextVar
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
        status = 404

    class _Result:
        status = UiPathRuntimeStatus.FAULTED
        error = _Error()

    dto = _job_api._to_result_dto("job-1", 3, _Result(), "out.args")

    assert (dto.jobKey, dto.resumeVersion) == ("job-1", 3)
    assert dto.status == _job_api.ExecutorJobStatus.FAULTED.value
    assert dto.outputArgumentsFilePath == "out.args"
    assert dto.outputArguments is None
    assert dto.error is not None
    # Every field, so a swapped Title/Detail (a stack trace shown as the error's title in the
    # job's failure record) cannot pass.
    assert (
        dto.error.code,
        dto.error.title,
        dto.error.detail,
        dto.error.category,
        dto.error.status,
    ) == ("BOOM", "It broke", "stack", "User", 404)


def test_to_result_dto_defaults_to_successful_without_error():
    class _Result:
        status = UiPathRuntimeStatus.SUCCESSFUL
        error = None

    dto = _job_api._to_result_dto("j", None, _Result(), "p.args")
    assert dto.status == _job_api.ExecutorJobStatus.SUCCESSFUL.value
    assert dto.resumeVersion is None
    assert dto.error is None


def test_to_result_dto_maps_suspended():
    """Mapping only. Suspend never reaches SetResult -- the runtime delivers SUCCESSFUL/FAULTED
    alone and the peer resolves a suspended job from output.json. Do not read this as the
    suspend path being carried over IPC."""

    class _Result:
        status = UiPathRuntimeStatus.SUSPENDED
        error = None

    dto = _job_api._to_result_dto("j", None, _Result(), "p.args")
    assert dto.status == _job_api.ExecutorJobStatus.SUSPENDED.value


def test_to_result_dto_maps_stopped():
    class _Result:
        status = "stopped"
        error = None

    dto = _job_api._to_result_dto("j", None, _Result(), "p.args")
    assert dto.status == _job_api.ExecutorJobStatus.STOPPED.value


def test_to_result_dto_reports_an_unknown_status_as_faulted():
    class _Result:
        status = "something-new"
        error = None

    dto = _job_api._to_result_dto("j", None, _Result(), "p.args")
    assert dto.status == _job_api.ExecutorJobStatus.FAULTED.value


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

    Guards our half of the wire contract: every DTO is camelCase, as the peer declares them.
    """
    serialization = pytest.importorskip("uipath_ipc.wire.serialization")
    to_wire = serialization.to_wire

    result_keys = set(
        to_wire(
            _job_api.PythonJobResultDto(jobKey="j", outputArgumentsFilePath="p.args")
        )
    )
    assert result_keys == {
        "jobKey",
        "resumeVersion",
        "status",
        "outputArguments",
        "outputArgumentsFilePath",
        "info",
        "error",
    }
    assert set(to_wire(_job_api.PythonJobLogDto(jobKey="j", message="m"))) == {
        "jobKey",
        "resumeVersion",
        "message",
        "logLevel",
    }
    assert set(to_wire(_job_api.JobExecutorError(code="c"))) == {
        "code",
        "title",
        "detail",
        "category",
        "status",
    }


def _isolated_output_sinks(monkeypatch) -> Any:
    """Read the sinks back through the REAL ContextVars.

    A dict would record that something was installed but not *where*: installing from the wrong
    thread or task would keep every test green while the job, looking the value up in its own
    context, found nothing. Fresh ContextVars per test keep that observable and stop one test's
    sinks leaking into the next.
    """
    from uipath.runtime import output_sinks

    monkeypatch.setattr(
        output_sinks, "_log_handler", ContextVar("test_log_handler", default=None)
    )
    monkeypatch.setattr(
        output_sinks, "_result_sink", ContextVar("test_result_sink", default=None)
    )

    class _Installed:
        def __getitem__(self, key: str) -> Any:
            if key == "handler":
                return output_sinks.get_log_handler()
            if key == "sink":
                return output_sinks.get_result_sink()
            raise KeyError(key)

    return _Installed()


def test_install_wires_log_handler_and_result_sink(monkeypatch):
    captured = _isolated_output_sinks(monkeypatch)
    logs: list[Any] = []
    results: list[Any] = []

    class _Callback:
        async def SendLog(self, dto: Any) -> None:
            logs.append(dto)

        async def SetResult(self, dto: Any) -> bool:
            results.append(dto)
            return True

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        _job_api.install_runtime_sinks("job-7", 2, _Callback(), loop)

        # The log handler forwards each record, tagged with the run it belongs to.
        handler = captured["handler"]
        handler.emit(
            logging.LogRecord("n", logging.WARNING, "p", 1, "hi %s", ("there",), None)
        )
        await handler.aflush_pending()
        assert (logs[0].jobKey, logs[0].resumeVersion) == ("job-7", 2)
        assert logs[0].message == "hi there"
        assert logs[0].logLevel == _job_api.LogLevel.WARNING.value

        # The result sink maps the result and calls SetResult, off a worker thread, for the ack.
        class _Result:
            status = UiPathRuntimeStatus.SUCCESSFUL
            error = None

        sink = captured["sink"]
        await asyncio.to_thread(sink, _Result(), "out.args")
        assert (results[0].jobKey, results[0].resumeVersion) == ("job-7", 2)
        assert results[0].outputArgumentsFilePath == "out.args"

    asyncio.run(scenario())


def test_an_unformattable_record_does_not_escape_emit(monkeypatch):
    """A mid-flight send failure is covered by the broken-channel test; this is the sync path."""
    captured = _isolated_output_sinks(monkeypatch)

    class _Callback:
        async def SendLog(self, log: Any) -> None:
            return None

    loop = asyncio.new_event_loop()
    try:
        _job_api.install_runtime_sinks(JOB_ID, None, _Callback(), loop)
        handler = captured["handler"]
        handled: list[Any] = []
        monkeypatch.setattr(handler, "handleError", handled.append)
        # %d against a str: formatting raises inside emit.
        handler.emit(logging.LogRecord("n", logging.INFO, "p", 1, "%d", ("x",), None))
        assert len(handled) == 1
        assert handler._snapshot() == []
    finally:
        loop.close()


def test_transport_and_self_logs_never_ride_the_ipc_channel(monkeypatch):
    captured = _isolated_output_sinks(monkeypatch)
    sent: list[Any] = []
    forwarded = threading.Event()

    class _Callback:
        async def SendLog(self, dto: Any) -> None:
            sent.append(dto)
            forwarded.set()

    buf = io.StringIO()
    monkeypatch.setattr(sys, "__stderr__", buf)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        _job_api.install_runtime_sinks("job-6", None, _Callback(), loop)
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

    assert [dto.message for dto in sent] == ["job line"]
    assert buf.getvalue().count("internal chatter") == 2


def test_rejected_result_is_reported(monkeypatch):
    captured = _isolated_output_sinks(monkeypatch)

    class _Callback:
        async def SetResult(self, dto: Any) -> bool:
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
        _job_api.install_runtime_sinks("job-8", None, _Callback(), loop)
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
    _isolated_output_sinks(monkeypatch)
    landed: list[str] = []

    class _Callback:
        async def SendLog(self, dto: Any) -> None:
            await asyncio.sleep(0.2)
            landed.append(dto.message)

    class _Client:
        async def aclose(self) -> None:
            return None

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    handler = _job_api.install_runtime_sinks("job-7", None, _Callback(), loop)
    assert handler is not None
    handler.emit(logging.LogRecord("j", logging.INFO, "p", 1, "tail line", (), None))

    conn = _job_api._HandlerIpcConnection(_Client(), loop, thread, handler)
    conn._shutdown()

    assert landed == ["tail line"]


def test_result_delivery_failure_is_swallowed_and_logged(monkeypatch):
    captured = _isolated_output_sinks(monkeypatch)

    class _Callback:
        async def SetResult(self, dto: Any) -> bool:
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
        _job_api.install_runtime_sinks("job-9", None, _Callback(), loop)
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


def test_clear_is_a_noop_without_the_runtime(monkeypatch):
    # Teardown still has to work on an older runtime -- only install refuses (see the test below).
    monkeypatch.setitem(sys.modules, "uipath.runtime.output_sinks", None)
    _job_api.clear_runtime_sinks()


def test_connect_installs_sinks_and_disconnect_clears(monkeypatch):
    pytest.importorskip("uipath_ipc")
    captured = _isolated_output_sinks(monkeypatch)

    class _Api(_job_api.IPythonJobApi):
        async def SendLog(self, log: Any) -> None:
            return None

        async def SetResult(self, result: Any) -> bool:
            return True

    pipe = _unique_jobapi_pipe()
    stop = _serve_jobapi_in_background(pipe, _Api())
    try:

        async def scenario() -> None:
            # The context manager, not the two halves: cli_run.py only ever uses this, and a
            # wiring mistake inside it would leave every assertion below untouched.
            async with _job_api.handler_ipc_connection(pipe, JOB_ID, None):
                assert captured["handler"] is not None
                assert captured["sink"] is not None

            assert captured["handler"] is None
            assert captured["sink"] is None

        asyncio.run(scenario())
    finally:
        stop()


def test_connect_fails_loudly_when_the_pipe_is_unreachable(monkeypatch):
    pytest.importorskip("uipath_ipc")
    _isolated_output_sinks(monkeypatch)

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
        _job_api.connect_handler_ipc("uipath-jobapi-does-not-exist-12345", JOB_ID, None)

    assert live() == before


def test_a_broken_log_channel_is_reported_once_to_stderr(monkeypatch):
    _isolated_output_sinks(monkeypatch)

    buf = io.StringIO()
    monkeypatch.setattr(sys, "__stderr__", buf)

    class _Callback:
        async def SendLog(self, log: Any) -> None:
            raise RuntimeError("pipe is gone")

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        handler = _job_api.install_runtime_sinks(JOB_ID, None, _Callback(), loop)
        assert handler is not None
        for i in range(4):
            handler.emit(
                logging.LogRecord("job", logging.INFO, __file__, 1, f"m{i}", None, None)
            )
        handler.flush_pending(timeout=5.0)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5.0)
        loop.close()

    out = buf.getvalue()
    assert "no longer reaching the handler" in out, out
    assert "pipe is gone" in out
    assert out.count("no longer reaching the handler") == 1, out


def test_a_cancelled_send_is_reported_like_any_other_failure(monkeypatch):
    """`future.exception()` RAISES for a cancelled future, so this arm needs its own case."""
    _isolated_output_sinks(monkeypatch)
    buf = io.StringIO()
    monkeypatch.setattr(sys, "__stderr__", buf)

    loop = asyncio.new_event_loop()
    try:
        handler = _job_api._IpcLogHandler(JOB_ID, None, object(), loop)
        cancelled: Future[object] = Future()
        assert cancelled.cancel()

        handler._settled(cancelled)
    finally:
        loop.close()

    assert "no longer reaching the handler" in buf.getvalue()


def test_missing_output_sinks_fails_loudly(monkeypatch):
    """Silently returning None would lose the job: the peer has already stopped watching the file."""
    monkeypatch.setitem(sys.modules, "uipath.runtime.output_sinks", None)

    with pytest.raises(RuntimeError, match="uipath-runtime"):
        _job_api.install_runtime_sinks(JOB_ID, None, object(), asyncio.new_event_loop())


def test_the_frame_cap_matches_the_dotnet_peer():
    """Both .NET servers on this contract accept 30 MB; uipath-ipc would otherwise default to 2."""
    from uipath_ipc.wire import MAX_PAYLOAD_BYTES

    assert _job_api._MAX_MESSAGE_BYTES == 30 * 1024 * 1024
    assert _job_api._MAX_MESSAGE_BYTES > MAX_PAYLOAD_BYTES


def _live_ipc_threads() -> int:
    return len(
        [
            t
            for t in threading.enumerate()
            if t.name == "uipath-handler-ipc" and t.is_alive()
        ]
    )


@pytest.mark.parametrize(
    "job_id",
    [
        None,
        "",
        " ",
        "job-1",
        "not-a-guid",
        "00000000-0000-0000-0000-000000000000",  # Guid.Empty: parses, routes nowhere
        "00000000-0000-0000-0000-00000000000",  # a digit short: malformed, not empty
    ],
)
def test_connect_without_a_real_job_id_fails_fast(job_id):
    before = _live_ipc_threads()
    with pytest.raises(RuntimeError, match="UIPATH_JOB_KEY"):
        _job_api.connect_handler_ipc("pipe", job_id, None)
    assert _live_ipc_threads() == before


@pytest.mark.parametrize("job_id", [None, "", "job-1"])
async def test_handler_ipc_connection_without_a_real_job_id_fails_fast(job_id):
    with pytest.raises(RuntimeError, match="UIPATH_JOB_KEY"):
        async with _job_api.handler_ipc_connection("pipe", job_id, None):
            pass


_jobapi_pipe_counter = 0


def _unique_jobapi_pipe() -> str:
    global _jobapi_pipe_counter
    _jobapi_pipe_counter += 1
    return f"uipath-jobapi-test-{os.getpid()}-{_jobapi_pipe_counter}"


def _serve_jobapi_in_background(pipe: str, api: Any):
    """Host ``api`` as IPythonJobApi on ``pipe`` in a daemon thread; return a stop() callable.

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
            services={_job_api.IPythonJobApi: api},
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
    captured = _isolated_output_sinks(monkeypatch)
    received: dict[str, Any] = {}

    class _Api(_job_api.IPythonJobApi):
        async def SendLog(self, log: Any) -> None:
            received.setdefault("logs", []).append(log)

        async def SetResult(self, result: Any) -> bool:
            # The server deserializes against the contract's typed signature, so result arrives as a
            # real PythonJobResultDto (this also exercises the wire round-trip of the DTO).
            received["result"] = result
            return True

    class _Result:
        status = UiPathRuntimeStatus.SUCCESSFUL
        error = None

    pipe = _unique_jobapi_pipe()
    stop = _serve_jobapi_in_background(pipe, _Api())
    try:

        async def scenario() -> None:
            conn = _job_api.connect_handler_ipc(pipe, JOB_ID_2, 1)
            # A log line has to survive the round trip too, not just the result.
            captured["handler"].emit(
                logging.LogRecord(
                    "job", logging.WARNING, "p", 1, "over %s", ("ipc",), None
                )
            )
            # Call the sink ON this loop's thread, exactly as the runtime's __exit__ does. Before the
            # fix this deadlocked the loop the ack was scheduled on; now it completes.
            started = time.monotonic()
            captured["sink"](_Result(), "out.args")
            elapsed = time.monotonic() - started

            # Assert BEFORE any await. Deadlocked, the sink burns _SET_RESULT_TIMEOUT_S and gives
            # up; the queued ack then completes during the await below and the result shows up
            # anyway, so anything asserted after an await passes either way.
            assert "result" in received, (
                "SetResult did not complete on the caller's loop thread"
            )
            assert elapsed < 5, (
                f"the sink blocked for {elapsed:.1f}s — the ack could not run"
            )

            await _job_api.disconnect_handler_ipc(conn)

        asyncio.run(scenario())
    finally:
        stop()

    # The log half of the contract, asserted on the wire rather than against a fake.
    assert "logs" in received, "SendLog never arrived over the pipe"
    entry = received["logs"][0]
    assert (entry.jobKey, entry.resumeVersion) == (JOB_ID_2, 1)
    assert entry.message == "over ipc"
    assert entry.logLevel == _job_api.LogLevel.WARNING.value

    assert "result" in received, (
        "SetResult never arrived — the result sink deadlocked/timed out"
    )
    dto = received["result"]
    assert (dto.jobKey, dto.resumeVersion) == (JOB_ID_2, 1)
    assert dto.outputArgumentsFilePath == "out.args"
    assert dto.status == _job_api.ExecutorJobStatus.SUCCESSFUL.value
