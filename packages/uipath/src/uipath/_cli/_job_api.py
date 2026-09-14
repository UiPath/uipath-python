"""The job-invocation IPC contract and the glue that routes a job's logs and result over it."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from concurrent.futures import Future
from concurrent.futures import wait as _futures_wait
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, TypeGuard

logger = logging.getLogger(__name__)

_SET_RESULT_TIMEOUT_S = 30.0
_LOG_FLUSH_TIMEOUT_S = 5.0
_IPC_REQUEST_TIMEOUT_S = 30.0

_NO_IPC_LOGGERS = ("uipath_ipc", __name__)


class LogLevel(IntEnum):
    """Log-level wire values."""

    TRACE = 0
    DEBUG = 1
    INFORMATION = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5
    NONE = 6


class ExecutorJobStatus(IntEnum):
    """Job-status wire values."""

    RUNNING = 1
    FAULTED = 2
    SUCCESSFUL = 3
    STOPPED = 4
    SUSPENDED = 5


@dataclass
class JobLogDto:
    """A log entry; field names are the wire keys (do not rename)."""

    Message: str = ""
    LogLevel: int = LogLevel.INFORMATION.value


@dataclass
class JobExecutorError:
    """A result error; field names are the wire keys (do not rename)."""

    Code: str | None = None
    Title: str | None = None
    Detail: str | None = None
    Category: str | None = None
    Status: int | None = None


@dataclass
class JobResultDto:
    """The final result; field names are the wire keys (do not rename)."""

    id: str = ""
    status: int = ExecutorJobStatus.SUCCESSFUL.value
    outputArguments: Any = None
    outputArgumentsFilePath: str | None = None
    info: str | None = None
    error: JobExecutorError | None = None


class IJobInvocationCommonApi(ABC):
    """The job-invocation contract: logs + the final result. The class name is the endpoint key."""

    @abstractmethod
    async def SendLog(self, jobId: str, log: JobLogDto) -> None:
        """Forward one log entry."""

    @abstractmethod
    async def SetResult(self, jobId: str, result: JobResultDto) -> bool:
        """Submit the final result."""


def _to_log_level(levelno: int) -> int:
    if levelno >= logging.CRITICAL:
        return LogLevel.CRITICAL
    if levelno >= logging.ERROR:
        return LogLevel.ERROR
    if levelno >= logging.WARNING:
        return LogLevel.WARNING
    if levelno >= logging.INFO:
        return LogLevel.INFORMATION
    if levelno >= logging.DEBUG:
        return LogLevel.DEBUG
    return LogLevel.TRACE


_EXECUTOR_STATUS: dict[str, int] = {
    "successful": ExecutorJobStatus.SUCCESSFUL.value,
    "faulted": ExecutorJobStatus.FAULTED.value,
    "suspended": ExecutorJobStatus.SUSPENDED.value,
}


def _to_result_dto(
    job_id: str, result: Any, output_arguments_file_path: str
) -> JobResultDto:
    error = None
    if result is not None and getattr(result, "error", None) is not None:
        category = result.error.category
        error = JobExecutorError(
            Code=result.error.code,
            Title=result.error.title,
            Detail=result.error.detail,
            Category=getattr(category, "value", category),
            Status=result.error.status,
        )
    raw_status = getattr(result, "status", None)
    status_key = str(getattr(raw_status, "value", raw_status) or "successful").lower()
    return JobResultDto(
        id=job_id,
        status=_EXECUTOR_STATUS.get(status_key, ExecutorJobStatus.SUCCESSFUL.value),
        outputArgumentsFilePath=output_arguments_file_path,
        error=error,
    )


def _write_original_stderr(text: str) -> None:
    stream = sys.__stderr__
    if stream is None:
        return
    try:
        stream.write(text + "\n")
        stream.flush()
    except Exception:
        pass


def _to_original_stderr(handler: logging.Handler, record: logging.LogRecord) -> None:
    _write_original_stderr(handler.format(record))


class _IpcLogHandler(logging.Handler):
    """Forwards each log record to the callback."""

    def __init__(
        self, job_id: str, callback: Any, loop: asyncio.AbstractEventLoop
    ) -> None:
        super().__init__()
        self._job_id = job_id
        self._callback = callback
        self._loop = loop
        self._pending: set[Future[object]] = set()
        self._pending_lock = threading.Lock()
        self._reported_failure = False

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(_NO_IPC_LOGGERS):
            _to_original_stderr(self, record)
            return
        try:
            message = self.format(record)
            dto = JobLogDto(Message=message, LogLevel=_to_log_level(record.levelno))
            future = asyncio.run_coroutine_threadsafe(
                self._callback.SendLog(self._job_id, dto), self._loop
            )
            with self._pending_lock:
                self._pending.add(future)
            future.add_done_callback(self._settled)
        except Exception:
            self.handleError(record)

    def _settled(self, future: "Future[object]") -> None:
        with self._pending_lock:
            self._pending.discard(future)
        try:
            error: BaseException | None = future.exception()
        except BaseException as e:  # cancelled
            error = e
        if error is None:
            return
        with self._pending_lock:
            first = not self._reported_failure
            self._reported_failure = True
        if first:
            # Once per handler: a broken channel fails every later send too.
            _write_original_stderr(
                f"uipath: job logs are no longer reaching the handler ({error!r}); "
                "further log-delivery errors for this job are suppressed."
            )

    def _snapshot(self) -> "list[Future[object]]":
        with self._pending_lock:
            return list(self._pending)

    def flush_pending(self, timeout: float = _LOG_FLUSH_TIMEOUT_S) -> None:
        # Blocks; only safe off the sink loop's own thread.
        pending = self._snapshot()
        if pending:
            _futures_wait(pending, timeout=timeout)

    async def aflush_pending(self, timeout: float = _LOG_FLUSH_TIMEOUT_S) -> None:
        pending = self._snapshot()
        if not pending:
            return
        await asyncio.wait([asyncio.wrap_future(f) for f in pending], timeout=timeout)


def install_runtime_sinks(
    job_id: str, callback: Any, loop: asyncio.AbstractEventLoop
) -> "_IpcLogHandler | None":
    """Install the log + result sinks, forwarding to ``callback`` on ``loop``.

    ``loop`` must run on a different thread than the one the sinks are invoked on, or the result ack
    deadlocks. No-op if the sinks aren't available.
    """
    try:
        from uipath.runtime.output_sinks import (
            set_log_handler,
            set_result_sink,
        )
    except ImportError:
        return None

    handler = _IpcLogHandler(job_id, callback, loop)
    handler.setFormatter(logging.Formatter("%(message)s"))

    def _result_sink(result: Any, output_arguments_file_path: str) -> None:
        dto = _to_result_dto(job_id, result, output_arguments_file_path)
        try:
            future = asyncio.run_coroutine_threadsafe(
                callback.SetResult(job_id, dto), loop
            )
            if future.result(timeout=_SET_RESULT_TIMEOUT_S) is False:
                logger.error(
                    "The handler rejected the job result (SetResult returned false)"
                )
        except Exception:
            logger.exception("Failed to deliver job result over IPC (SetResult)")

    set_log_handler(handler)
    set_result_sink(_result_sink)
    return handler


def clear_runtime_sinks() -> None:
    """Clear the installed sinks."""
    try:
        from uipath.runtime.output_sinks import set_log_handler, set_result_sink
    except ImportError:
        return
    set_log_handler(None)
    set_result_sink(None)


def _stop_loop_thread(
    loop: asyncio.AbstractEventLoop, thread: threading.Thread, timeout: float
) -> None:
    # Never raise here: a wedged thread leaves the loop running, and close() would mask the job's outcome.
    try:
        loop.call_soon_threadsafe(loop.stop)
    except Exception:
        pass
    thread.join(timeout=timeout)
    if thread.is_alive():
        return
    try:
        loop.close()
    except Exception:
        pass


def _new_ipc_event_loop() -> asyncio.AbstractEventLoop:
    """A fresh event loop for the connection's thread (Proactor on Windows, required for named pipes)."""
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


class _HandlerIpcConnection:
    """An IPC client on its own loop/thread, so the synchronous result ack can't deadlock the job's loop."""

    def __init__(
        self,
        client: Any,
        loop: asyncio.AbstractEventLoop,
        thread: threading.Thread,
        log_handler: "_IpcLogHandler | None" = None,
    ) -> None:
        self._client = client
        self._loop = loop
        self._thread = thread
        self._log_handler = log_handler

    def _shutdown(self) -> None:
        """Close the client and stop its loop/thread."""
        if self._log_handler is not None:
            self._log_handler.flush_pending()
        try:
            asyncio.run_coroutine_threadsafe(self._client.aclose(), self._loop).result(
                timeout=_SET_RESULT_TIMEOUT_S
            )
        except Exception:
            pass
        _stop_loop_thread(self._loop, self._thread, _SET_RESULT_TIMEOUT_S)


def is_wire_job_id(job_id: str | None) -> TypeGuard[str]:
    """The peer types the job id as a Guid, and rejects anything it can't parse as one."""
    try:
        uuid.UUID(str(job_id))
    except ValueError:
        return False
    return True


def connect_handler_ipc(pipe: str, job_id: str | None) -> _HandlerIpcConnection:
    """Dial ``pipe`` on a dedicated loop/thread and install the sinks (see ``_HandlerIpcConnection``)."""
    if not is_wire_job_id(job_id):
        raise RuntimeError(
            f"--handler-ipc-pipe needs UIPATH_JOB_KEY to be a job id; got {job_id!r}."
        )

    try:
        from uipath_ipc import IpcClient, NamedPipeClientTransport
    except ImportError as e:
        raise RuntimeError(
            "--handler-ipc-pipe requires the 'uipath-ipc' package. Install it (pip install 'uipath[ipc]')."
        ) from e

    loop = _new_ipc_event_loop()
    thread = threading.Thread(
        target=loop.run_forever, name="uipath-handler-ipc", daemon=True
    )
    thread.start()

    async def _build() -> Any:
        transport = NamedPipeClientTransport(pipe)
        # Dial now: execution.log is already suppressed, so a dead pipe would lose every line in silence.
        try:
            _, writer = await transport.connect()
        except Exception as e:
            raise RuntimeError(
                f"Could not reach the handler IPC pipe {pipe!r}: {e}"
            ) from e
        writer.close()
        client = IpcClient(transport=transport, request_timeout=_IPC_REQUEST_TIMEOUT_S)
        proxy = client.get_proxy(IJobInvocationCommonApi)  # type: ignore[type-abstract]
        return client, proxy

    try:
        client, proxy = asyncio.run_coroutine_threadsafe(_build(), loop).result(
            timeout=_SET_RESULT_TIMEOUT_S
        )
    except BaseException:
        _stop_loop_thread(loop, thread, _SET_RESULT_TIMEOUT_S)
        raise
    # Install in the caller's context: the sinks are contextvars, read in the job's own context at teardown.
    handler = install_runtime_sinks(job_id, proxy, loop)
    return _HandlerIpcConnection(client, loop, thread, handler)


async def disconnect_handler_ipc(conn: _HandlerIpcConnection) -> None:
    """Clear the sinks and tear down the connection."""
    clear_runtime_sinks()
    await asyncio.to_thread(conn._shutdown)


@contextlib.asynccontextmanager
async def handler_ipc_connection(
    pipe: str | None, job_id: str | None
) -> AsyncIterator[Any]:
    """Connect (if ``pipe`` is set) and always disconnect on exit; yields the connection or None."""
    conn = connect_handler_ipc(pipe, job_id) if pipe is not None else None
    try:
        yield conn
    finally:
        if conn is not None:
            await disconnect_handler_ipc(conn)
