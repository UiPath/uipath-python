"""uipath-ipc runtime transport — the IPC contract, DTOs, and service.

Split out from ``cli_server`` so the wire-dictated PascalCase names (methods and
DTO fields) live in one file. Their casing is forced by the .NET/CoreIpc peer:
the serializer maps method and field names verbatim (no alias mechanism), so
they cannot be Python-idiomatic without breaking interop. The Sonar naming
rules (python:S100 methods, python:S116 fields) are suppressed for this file
only (see ``sonar-project.properties``), keeping the rest of the tree strict.

Served alongside the HTTP channel by ``cli_server`` whenever a ``--server-socket``
is given. Older servers served HTTP only; the .NET Handler copes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from uipath_ipc import IpcServer, NamedPipeServerTransport

from ._utils._console import ConsoleLogger

console = ConsoleLogger()


@dataclass
class PythonRunRequest:
    """Mirrors the .NET PythonRunRequest DTO. PascalCase fields match the wire keys."""

    JobKey: str = ""
    Command: str = ""
    Args: str | None = None
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
        # Imported here (not at module top) to keep the job core one-directional:
        # cli_server imports this module, so this module reaches back lazily.
        from .cli_server import COMMANDS, _run_command_isolated, parse_args

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
        # Cancellation is not wired into the job core yet — accept the request and
        # no-op so the .NET side gets a clean response. Real cancellation lands here.
        console.info(f"StopJob requested for {job_key} (no-op)")
        return True


async def start_ipc_server(pipe_name: str) -> None:
    """Serve the Python runtime over a uipath-ipc named pipe until it is closed."""
    from .cli_server import _state

    _state.init()
    server = IpcServer(
        transport=NamedPipeServerTransport(pipe_name),
        services={IPythonRuntimeServer: PythonRuntimeService()},
        request_timeout=None,  # jobs are long-running; no server-side timeout
    )
    console.success(f"IPC server listening on pipe '{pipe_name}'")
    async with server:
        await server.serve_forever()
