import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ._server_core import COMMANDS, _run_command_isolated, _state, parse_args
from ._utils._console import ConsoleLogger

if TYPE_CHECKING:
    from uipath_ipc import Message
else:
    # Optional dependency (uipath[ipc]): the Register annotation stays a string forward-ref so this
    # placeholder is never subscripted at import — resolved to the real Message only at dispatch.
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
    # Per-job opt-in (default False so it stays off unless explicitly set).
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
    async def RunJob(self, request: PythonServerRunRequest) -> PythonServerRunJobResult:
        """Run a job → PythonServerRunJobResult(ExitCode, Error)."""

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
            # Derived per request, never stored: a captured callback goes stale on reconnect/restart.
            from ._job_api import (
                IJobInvocationCommonApi,
                clear_runtime_sinks,
                install_runtime_sinks,
            )

            callback = None
            client = message.client if message is not None else None
            if client is not None:
                try:
                    callback = client.get_callback(IJobInvocationCommonApi)  # type: ignore[type-abstract]
                except Exception:
                    callback = None
            if callback is None:
                return PythonServerRunJobResult(
                    ExitCode=1,
                    Error="StreamOutputOverIpc was requested but no IPC callback is available",
                )

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

        # Drain in-flight sends by awaiting: they share this loop, and the peer may unregister the
        # job the moment this response lands.
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
    try:
        from uipath_ipc import IpcServer, NamedPipeServerTransport
    except ImportError as e:
        raise RuntimeError(
            "The uipath-ipc channel was requested (--ipc-pipe) but the 'uipath-ipc' "
            "package is not installed in this environment. Install it (pip install "
            "'uipath[ipc]') or omit --ipc-pipe to serve HTTP only."
        ) from e

    _state.init()

    # Register the default runtime factory (idempotent) so the server works when started outside the CLI.
    from uipath._cli import _ensure_runtime_initialized

    _ensure_runtime_initialized()

    server = IpcServer(
        transport=NamedPipeServerTransport(pipe_name),
        services={IPythonRuntimeServer: PythonRuntimeService()},
        request_timeout=None,  # jobs are long-running; no server-side timeout
    )
    console.success(f"IPC server listening on pipe '{pipe_name}'")
    async with server:
        await server.serve_forever()
