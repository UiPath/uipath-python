"""uipath-ipc runtime transport — the IPC contract, DTOs, and service.

The PascalCase method and field names are dictated by the .NET/CoreIpc peer
(the serializer maps them verbatim), so Sonar's S100/S116 naming rules are
suppressed for this file only (see ``sonar-project.properties``).

``uipath-ipc`` is an optional dependency (the ``ipc`` extra): it is imported
lazily inside ``start_ipc_server`` so this module — and HTTP-only serving —
works without it. The DTOs and the contract below are pure stdlib and never
reference it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ._server_core import COMMANDS, _run_command_isolated, _state, parse_args
from ._utils._console import ConsoleLogger

console = ConsoleLogger()


@dataclass
class PythonRunRequest:
    """Mirrors the .NET PythonRunRequest DTO. PascalCase fields match the wire keys."""

    JobKey: str = ""
    Command: str = ""
    # The .NET peer sends a single string; HTTP callers and tests may pass a
    # pre-split list. parse_args accepts both.
    Args: str | list[str] | None = None
    WorkingDirectory: str | None = None
    EnvironmentVariables: dict[str, str] = field(default_factory=dict)


@dataclass
class PythonRunResult:
    """Mirrors the .NET PythonRunResult DTO."""

    ExitCode: int = 0
    Error: str | None = None


class IPythonRuntimeServer(ABC):
    """Contract the .NET job executor calls over uipath-ipc."""

    @abstractmethod
    async def StartJob(self, request: PythonRunRequest) -> PythonRunResult:
        """Run a job → PythonRunResult(ExitCode, Error)."""

    @abstractmethod
    async def StopJob(self, job_key: str) -> bool:
        """Cancel a running job by key (bool return avoids fire-and-forget)."""


class PythonRuntimeService(IPythonRuntimeServer):
    """``IPythonRuntimeServer`` implementation backed by run/debug/eval."""

    async def StartJob(self, request: PythonRunRequest) -> PythonRunResult:
        command_name = request.Command
        if not isinstance(command_name, str) or not command_name:
            return PythonRunResult(
                ExitCode=1, Error="Missing or invalid field: 'Command'"
            )

        cmd = COMMANDS.get(command_name)
        if cmd is None:
            return PythonRunResult(ExitCode=1, Error=f"Unknown command: {command_name}")

        args = parse_args(request.Args)

        console.info(f"Starting job {request.JobKey}: {command_name} {args}")

        result = await _run_command_isolated(
            cmd, args, request.EnvironmentVariables, request.WorkingDirectory
        )
        # IPC contract (PythonRunResult) carries only ExitCode + Error.
        return PythonRunResult(ExitCode=result["ExitCode"], Error=result["Error"])

    async def StopJob(self, job_key: str) -> bool:
        console.info(f"StopJob requested for {job_key} (no-op)")
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
    server = IpcServer(
        transport=NamedPipeServerTransport(pipe_name),
        services={IPythonRuntimeServer: PythonRuntimeService()},
        request_timeout=None,  # jobs are long-running; no server-side timeout
    )
    console.success(f"IPC server listening on pipe '{pipe_name}'")
    async with server:
        await server.serve_forever()
