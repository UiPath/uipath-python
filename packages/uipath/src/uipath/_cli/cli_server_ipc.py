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
    """camelCase fields match the wire keys."""

    jobKey: str = ""
    resumeVersion: int | None = None
    command: str = ""
    # The peer sends a single string; HTTP callers and tests may pass a
    # pre-split list. parse_args accepts both.
    args: str | list[str] | None = None
    workingDirectory: str | None = None
    environmentVariables: dict[str, str] = field(default_factory=dict)
    streamOutputOverIpc: bool = False


@dataclass
class PythonServerStopJobRequest:
    jobKey: str = ""
    resumeVersion: int | None = None
    forceStop: bool = False


@dataclass
class PythonServerRunJobResult:
    exitCode: int = 0
    error: str | None = None


class IPythonRuntimeServer(ABC):
    """Contract the job executor calls over uipath-ipc."""

    @abstractmethod
    async def Register(self, message: "Message[None]") -> bool:
        """Prove the connection is up."""

    @abstractmethod
    async def RunJob(
        self, request: PythonServerRunRequest, *, message: "Message[None] | None" = None
    ) -> PythonServerRunJobResult:
        """Run a job → PythonServerRunJobResult(exitCode, error).

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
        command_name = request.command
        if not isinstance(command_name, str) or not command_name:
            return PythonServerRunJobResult(
                exitCode=1, error="Missing or invalid field: 'command'"
            )

        cmd = COMMANDS.get(command_name)
        if cmd is None:
            return PythonServerRunJobResult(
                exitCode=1, error=f"Unknown command: {command_name}"
            )

        args = parse_args(request.args)

        console.info(
            f"Running job {_run_id(request.jobKey, request.resumeVersion)}: {command_name} {args}"
        )

        on_run_start: "Any" = None
        on_run_end: "Any" = None
        installed: "list[Any]" = []
        if request.streamOutputOverIpc:
            # Never stored: a captured callback goes stale on reconnect/restart.
            from ._job_api import (
                IPythonJobApi,
                clear_runtime_sinks,
                install_runtime_sinks,
                is_wire_job_key,
            )

            if not is_wire_job_key(request.jobKey):
                return PythonServerRunJobResult(
                    exitCode=1,
                    error=f"streamOutputOverIpc needs a 'jobKey' that is a job key (Guid); got {request.jobKey!r}",
                )

            if message is None or message.client is None:
                return PythonServerRunJobResult(
                    exitCode=1,
                    error="streamOutputOverIpc is only available when RunJob is invoked over IPC",
                )

            # get_callback only wraps the connection, so this cannot tell us whether the peer
            # actually hosts the contract; a peer that doesn't shows up as a failing send.
            callback = message.client.get_callback(IPythonJobApi)  # type: ignore[type-abstract]

            loop = asyncio.get_running_loop()
            job_key = request.jobKey
            resume_version = request.resumeVersion

            def _install() -> None:
                installed.append(
                    install_runtime_sinks(job_key, resume_version, callback, loop)
                )

            on_run_start = _install
            on_run_end = clear_runtime_sinks

        result = await _run_command_isolated(
            cmd,
            args,
            request.environmentVariables,
            request.workingDirectory,
            on_run_start=on_run_start,
            on_run_end=on_run_end,
        )

        # Await, don't block: these share this loop, and the peer may unregister the job once this returns.
        for handler in installed:
            if handler is not None:
                await handler.aflush_pending()

        # IPC contract (PythonServerRunJobResult) carries only exitCode + error.
        return PythonServerRunJobResult(
            exitCode=result["ExitCode"], error=result["Error"]
        )

    async def StopJob(self, request: PythonServerStopJobRequest) -> bool:
        console.info(
            f"StopJob requested for {_run_id(request.jobKey, request.resumeVersion)} "
            f"(force={request.forceStop}) (no-op)"
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
