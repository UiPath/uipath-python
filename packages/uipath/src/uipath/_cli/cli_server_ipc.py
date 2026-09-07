import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._server_core import COMMANDS, _run_command_isolated, _state, parse_args
from ._utils._console import ConsoleLogger

if TYPE_CHECKING:
    from uipath_ipc import Message
else:
    # Optional dependency: only present when the uipath-ipc channel is served (uipath[ipc]).
    # The Register annotation stays a string forward-ref so this placeholder is never subscripted
    # at import; it is resolved (to the real Message) only during dispatch, which needs uipath-ipc.
    try:
        from uipath_ipc import Message
    except ImportError:  # pragma: no cover - no IPC means Register is never dispatched
        Message = object

console = ConsoleLogger()


def _run_id(job_key: str, resume_version: int | None) -> str:
    return job_key if resume_version is None else f"{job_key}-{resume_version}"


@dataclass
class PythonServerRunRequest:
    """PascalCase fields match the wire keys."""

    JobKey: str = ""
    ResumeVersion: int | None = None
    Command: str = ""
    # The peer sends a single string; HTTP callers and tests may pass a
    # pre-split list. parse_args accepts both.
    Args: str | list[str] | None = None
    WorkingDirectory: str | None = None
    EnvironmentVariables: dict[str, str] = field(default_factory=dict)


@dataclass
class PythonServerStopJobRequest:
    JobKey: str = ""
    ResumeVersion: int | None = None
    ForceStop: bool = False


@dataclass
class PythonServerRunJobResult:
    ExitCode: int = 0
    Error: str | None = None


class IPythonRuntimeServer(ABC):
    """Contract the job executor calls over uipath-ipc."""

    @abstractmethod
    async def Register(self, message: "Message[None]") -> bool:
        """Prove the connection is up, and grab the caller's log-sink callback.

        The injected ``message`` is a reach-back handle (it carries no wire
        argument): ``message.client.get_callback`` reaches the handler's
        ``IIpcLogSink`` over this same pipe, which pooled jobs stream their logs
        into.
        """

    @abstractmethod
    async def RunJob(self, request: PythonServerRunRequest) -> PythonServerRunJobResult:
        """Run a job → PythonServerRunJobResult(ExitCode, Error)."""

    @abstractmethod
    async def StopJob(self, request: PythonServerStopJobRequest) -> bool:
        """Cancel a running job by key (bool return avoids fire-and-forget)."""


class PythonRuntimeService(IPythonRuntimeServer):
    """``IPythonRuntimeServer`` implementation backed by run/debug/eval."""

    async def Register(self, message: "Message[None]") -> bool:
        _wire_pooled_log_sink(message)
        console.info("Runtime client registered.")
        return True

    async def RunJob(self, request: PythonServerRunRequest) -> PythonServerRunJobResult:
        command_name = request.Command
        if not isinstance(command_name, str) or not command_name:
            return PythonServerRunJobResult(
                ExitCode=1, Error="Missing or invalid field: 'Command'"
            )

        cmd = COMMANDS.get(command_name)
        if cmd is None:
            return PythonServerRunJobResult(
                ExitCode=1, Error=f"Unknown command: {command_name}"
            )

        args = parse_args(request.Args)

        console.info(
            f"Running job {_run_id(request.JobKey, request.ResumeVersion)}: {command_name} {args}"
        )

        result = await _run_command_isolated(
            cmd, args, request.EnvironmentVariables, request.WorkingDirectory
        )
        # IPC contract (PythonServerRunJobResult) carries only ExitCode + Error.
        return PythonServerRunJobResult(
            ExitCode=result["ExitCode"], Error=result["Error"]
        )

    async def StopJob(self, request: PythonServerStopJobRequest) -> bool:
        console.info(
            f"StopJob requested for {_run_id(request.JobKey, request.ResumeVersion)} "
            f"(force={request.ForceStop}) (no-op)"
        )
        return True


def _drain(future: "Future[object]") -> None:
    # Retrieve (and discard) a forwarded log's result so a failed one-way send never surfaces.
    try:
        future.exception()
    except BaseException:
        pass


def _wire_pooled_log_sink(message: "Message[None]") -> None:
    """Point the runtime's process-global log sink at this connection's IIpcLogSink callback.

    Pooled jobs run in this same process (``_run_command_isolated`` → a worker thread), so their
    logging can reach back to the handler over the pipe the handler dialed in on. The runtime raises
    each record to a process-global sink; here we make that sink forward to the handler's callback.

    Best-effort: log streaming is an add-on to the Register handshake, so any failure (an older
    uipath-runtime without the pooled sink API, or a peer hosting no callback) leaves jobs on their
    file+watcher path and never fails registration.
    """
    # A Message built without a caller handle has nothing to reach back to.
    client = message.client
    if client is None:
        return
    try:
        from uipath.runtime.jobapi import (  # type: ignore[import-untyped]
            IIpcLogSink,
            set_pooled_log_sink,
        )
    except ImportError:
        return  # runtime predates the pooled sink — nothing to wire; jobs keep the file path

    sink_proxy = client.get_callback(IIpcLogSink)
    loop = asyncio.get_running_loop()

    def _forward(job_id: str, log: object) -> None:
        # Runs on the job's worker thread: hand the one-way SendLog to the server loop and return at
        # once. A dropped log (pipe down) must never surface into the job, so failures are swallowed.
        future = asyncio.run_coroutine_threadsafe(sink_proxy.SendLog(job_id, log), loop)
        future.add_done_callback(_drain)

    set_pooled_log_sink(_forward)


async def start_ipc_server(pipe_name: str) -> None:
    """Serve the Python runtime over a uipath-ipc named pipe until it is closed."""
    try:
        from uipath_ipc import IpcServer, NamedPipeServerTransport
    except ImportError as e:
        raise RuntimeError(
            "The uipath-ipc channel was requested (--ipc-pipe) but the 'uipath-ipc' "
            "package is not installed in this environment. Install it (pip install "
            "'uipath[ipc]') or omit --ipc-pipe to serve HTTP only."
        ) from e

    _state.init()
    server = IpcServer(
        transport=NamedPipeServerTransport(pipe_name),
        services={IPythonRuntimeServer: PythonRuntimeService()},
        request_timeout=None,  # jobs are long-running; no server-side timeout
    )
    console.success(f"IPC server listening on pipe '{pipe_name}'")
    try:
        async with server:
            await server.serve_forever()
    finally:
        # Drop the process-global sink so it can't outlive this loop (matters if the server is
        # ever restarted in-process, e.g. in tests).
        try:
            from uipath.runtime.jobapi import set_pooled_log_sink

            set_pooled_log_sink(None)
        except ImportError:
            pass
