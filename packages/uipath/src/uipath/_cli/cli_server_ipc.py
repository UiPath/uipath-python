import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ._server_core import COMMANDS, _run_command_isolated, _state, parse_args
from ._utils._console import ConsoleLogger

if TYPE_CHECKING:
    from uipath_ipc import Message
else:
    # uipath-ipc is a base dependency, so this only fires on a broken install. The annotation stays a
    # string forward-ref, so this placeholder is never subscripted.
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
    StreamOutputOverIpc: bool = False


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
        """Prove the connection is up."""

    @abstractmethod
    async def RunJob(
        self, request: PythonServerRunRequest, *, message: "Message[None] | None" = None
    ) -> PythonServerRunJobResult:
        """Run a job → PythonServerRunJobResult(ExitCode, Error).

        ``message`` is injected by the dispatcher, which reads this contract — not the impl.
        """

    @abstractmethod
    async def StopJob(self, request: PythonServerStopJobRequest) -> bool:
        """Cancel a running job by key (bool return avoids fire-and-forget)."""


class PythonRuntimeService(IPythonRuntimeServer):
    """``IPythonRuntimeServer`` implementation backed by run/debug/eval."""

    async def Register(self, message: "Message[None]") -> bool:
        console.info("Runtime client registered.")
        return True

    async def RunJob(
        self, request: PythonServerRunRequest, *, message: "Message[None] | None" = None
    ) -> PythonServerRunJobResult:
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

        on_run_start: "Any" = None
        on_run_end: "Any" = None
        installed: "list[Any]" = []
        if request.StreamOutputOverIpc:
            # Never stored: a captured callback goes stale on reconnect/restart.
            from ._job_api import (
                IJobInvocationCommonApi,
                clear_runtime_sinks,
                install_runtime_sinks,
                is_wire_job_id,
            )

            if not is_wire_job_id(request.JobKey):
                return PythonServerRunJobResult(
                    ExitCode=1,
                    Error=f"StreamOutputOverIpc needs a 'JobKey' that is a job id; got {request.JobKey!r}",
                )

            if message is None or message.client is None:
                return PythonServerRunJobResult(
                    ExitCode=1,
                    Error="StreamOutputOverIpc is only available when RunJob is invoked over IPC",
                )

            # get_callback only wraps the connection, so this cannot tell us whether the peer
            # actually hosts the contract; a peer that doesn't shows up as a failing send.
            callback = message.client.get_callback(IJobInvocationCommonApi)  # type: ignore[type-abstract]

            loop = asyncio.get_running_loop()
            job_key = request.JobKey

            def _install() -> None:
                installed.append(install_runtime_sinks(job_key, callback, loop))

            on_run_start = _install
            on_run_end = clear_runtime_sinks

        result = await _run_command_isolated(
            cmd,
            args,
            request.EnvironmentVariables,
            request.WorkingDirectory,
            on_run_start=on_run_start,
            on_run_end=on_run_end,
        )

        # Await, don't block: these share this loop, and the peer may unregister the job once this returns.
        for handler in installed:
            if handler is not None:
                await handler.aflush_pending()

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


async def start_ipc_server(pipe_name: str) -> None:
    """Serve the Python runtime over a uipath-ipc named pipe until it is closed."""
    from uipath_ipc import IpcServer, NamedPipeServerTransport

    _state.init()

    from uipath._cli.runtimes import ensure_runtime_initialized

    ensure_runtime_initialized()

    from ._job_api import _MAX_MESSAGE_BYTES

    server = IpcServer(
        transport=NamedPipeServerTransport(pipe_name),
        services={IPythonRuntimeServer: PythonRuntimeService()},
        request_timeout=None,  # jobs are long-running; no server-side timeout
        max_message_size=_MAX_MESSAGE_BYTES,
    )
    console.success(f"IPC server listening on pipe '{pipe_name}'")
    async with server:
        await server.serve_forever()
