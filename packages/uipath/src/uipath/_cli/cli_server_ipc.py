from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ._server_core import COMMANDS, _run_command_isolated, _state, parse_args
from ._utils._console import ConsoleLogger

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
    async def Register(self) -> bool:
        """Prove the connection is up. No-op until there is something to register."""

    @abstractmethod
    async def RunJob(self, request: PythonServerRunRequest) -> PythonServerRunJobResult:
        """Run a job → PythonServerRunJobResult(ExitCode, Error)."""

    @abstractmethod
    async def StopJob(self, request: PythonServerStopJobRequest) -> bool:
        """Cancel a running job by key (bool return avoids fire-and-forget)."""


class PythonRuntimeService(IPythonRuntimeServer):
    """``IPythonRuntimeServer`` implementation backed by run/debug/eval."""

    async def Register(self) -> bool:
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
