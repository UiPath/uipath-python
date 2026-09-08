"""The job-invocation IPC contract and the glue that routes a job's logs and result over it."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from concurrent.futures import Future
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)

_SET_RESULT_TIMEOUT_S = 30.0


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


def _drain(future: "Future[object]") -> None:
    try:
        future.exception()
    except BaseException:
        pass


class _IpcLogHandler(logging.Handler):
    """Forwards each log record to the callback."""

    def __init__(
        self, job_id: str, callback: Any, loop: asyncio.AbstractEventLoop
    ) -> None:
        super().__init__()
        self._job_id = job_id
        self._callback = callback
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            dto = JobLogDto(Message=message, LogLevel=_to_log_level(record.levelno))
            future = asyncio.run_coroutine_threadsafe(
                self._callback.SendLog(self._job_id, dto), self._loop
            )
            future.add_done_callback(_drain)
        except Exception:
            self.handleError(record)


def install_runtime_sinks(
    job_id: str, callback: Any, loop: asyncio.AbstractEventLoop
) -> None:
    """Install the log + result sinks, forwarding to ``callback`` on ``loop``.

    ``loop`` must run on a different thread than the one the sinks are invoked on, or the result ack
    deadlocks. No-op if the sinks aren't available.
    """
    try:
        from uipath.runtime.output_sinks import (  # type: ignore[import-untyped]
            set_log_handler,
            set_result_sink,
        )
    except ImportError:
        return

    handler = _IpcLogHandler(job_id, callback, loop)
    handler.setFormatter(logging.Formatter("%(message)s"))

    def _result_sink(result: Any, output_arguments_file_path: str) -> None:
        dto = _to_result_dto(job_id, result, output_arguments_file_path)
        try:
            future = asyncio.run_coroutine_threadsafe(
                callback.SetResult(job_id, dto), loop
            )
            future.result(timeout=_SET_RESULT_TIMEOUT_S)
        except Exception:
            # Best-effort — a dropped result must be logged, not swallowed.
            logger.exception("Failed to deliver job result over IPC (SetResult)")

    set_log_handler(handler)
    set_result_sink(_result_sink)


def clear_runtime_sinks() -> None:
    """Clear the installed sinks."""
    try:
        from uipath.runtime.output_sinks import set_log_handler, set_result_sink
    except ImportError:
        return
    set_log_handler(None)
    set_result_sink(None)


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
    ) -> None:
        self._client = client
        self._loop = loop
        self._thread = thread

    def _shutdown(self) -> None:
        """Close the client and stop its loop/thread."""
        try:
            asyncio.run_coroutine_threadsafe(self._client.aclose(), self._loop).result(
                timeout=_SET_RESULT_TIMEOUT_S
            )
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=_SET_RESULT_TIMEOUT_S)
        self._loop.close()


def connect_handler_ipc(pipe: str, job_id: str) -> _HandlerIpcConnection:
    """Dial ``pipe`` on a dedicated loop/thread and install the sinks (see ``_HandlerIpcConnection``)."""
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
        client = IpcClient(transport=NamedPipeClientTransport(pipe))
        proxy = client.get_proxy(IJobInvocationCommonApi)  # type: ignore[type-abstract]
        return client, proxy

    try:
        client, proxy = asyncio.run_coroutine_threadsafe(_build(), loop).result(
            timeout=_SET_RESULT_TIMEOUT_S
        )
    except BaseException:
        # On failure, don't leak the loop/thread.
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=_SET_RESULT_TIMEOUT_S)
        loop.close()
        raise
    # Install in the caller's context, not on the IPC thread: the sinks are contextvars, resolved in
    # the job's own context at teardown. The ack still runs on `loop` (a separate thread) — no deadlock.
    install_runtime_sinks(job_id, proxy, loop)
    return _HandlerIpcConnection(client, loop, thread)


async def disconnect_handler_ipc(conn: _HandlerIpcConnection) -> None:
    """Clear the sinks and tear down the connection."""
    clear_runtime_sinks()
    # Off the caller's loop so joining the thread doesn't block it.
    await asyncio.to_thread(conn._shutdown)


@contextlib.asynccontextmanager
async def handler_ipc_connection(pipe: str | None, job_id: str) -> AsyncIterator[Any]:
    """Connect (if ``pipe`` is set) and always disconnect on exit; yields the connection or None."""
    conn = connect_handler_ipc(pipe, job_id) if pipe else None
    try:
        yield conn
    finally:
        if conn is not None:
            await disconnect_handler_ipc(conn)
