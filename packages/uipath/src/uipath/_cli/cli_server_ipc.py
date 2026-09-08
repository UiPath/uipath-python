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
        """Prove the connection is up and grab the caller's callback via ``message.client.get_callback``."""

    @abstractmethod
    async def RunJob(self, request: PythonServerRunRequest) -> PythonServerRunJobResult:
        """Run a job → PythonServerRunJobResult(ExitCode, Error)."""

    @abstractmethod
    async def StopJob(self, request: PythonServerStopJobRequest) -> bool:
        """Cancel a running job by key (bool return avoids fire-and-forget)."""


class PythonRuntimeService(IPythonRuntimeServer):
    """``IPythonRuntimeServer`` implementation backed by run/debug/eval."""

    def __init__(self) -> None:
        # The caller's callback, grabbed at Register (None until then).
        self._callback: Any = None
        self._loop: "asyncio.AbstractEventLoop | None" = None

    async def Register(self, message: "Message[None]") -> bool:
        client = message.client
        if client is not None:
            try:
                from ._job_api import IJobInvocationCommonApi

                self._callback = client.get_callback(IJobInvocationCommonApi)  # type: ignore[type-abstract]
                self._loop = asyncio.get_running_loop()
            except Exception:
                self._callback = (
                    None  # older runtime / no callback: jobs keep the file path
                )
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

        # Only when opted in and a callback exists. Install/clear the sinks INSIDE the job core's lock
        # (via the hooks) so they're bound only while THIS job runs.
        callback, loop = self._callback, self._loop
        on_run_start: "Any" = None
        on_run_end: "Any" = None
        if request.StreamOutputOverIpc and callback is not None and loop is not None:
            from ._job_api import clear_runtime_sinks, install_runtime_sinks

            job_key = request.JobKey
            on_run_start = lambda: install_runtime_sinks(job_key, callback, loop)  # noqa: E731
            on_run_end = clear_runtime_sinks

        result = await _run_command_isolated(
            cmd,
            args,
            request.EnvironmentVariables,
            request.WorkingDirectory,
            on_run_start=on_run_start,
            on_run_end=on_run_end,
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
    try:
        async with server:
            await server.serve_forever()
    finally:
        # Drop the sinks so they can't outlive this loop (matters on in-process restart).
        from ._job_api import clear_runtime_sinks

        clear_runtime_sinks()
