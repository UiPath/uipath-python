"""`uipath server` — serves the pre-warmed Python runtime over uipath-ipc.

Hosts ``IPythonRuntimeServer`` (Ping / StartJob / CancelJob) on a named pipe and
forwards StartJob to run/debug/eval; the .NET job executor connects as the
client. DTOs cross the wire as plain PascalCase dicts (matching the .NET DTOs).
"""

import asyncio
import importlib
import os
import shlex
import sys
import threading
import time
from abc import ABC, abstractmethod
from importlib.metadata import PackageNotFoundError, entry_points, version
from importlib.util import find_spec
from typing import Any

import click
from uipath_ipc import IpcServer, NamedPipeServerTransport, ipc_cancellable

from ._telemetry import track_command
from ._utils._console import ConsoleLogger
from .cli_debug import debug
from .cli_eval import eval
from .cli_run import run

console = ConsoleLogger()

IS_WINDOWS = sys.platform == "win32"

COMMANDS = {
    "run": run,
    "debug": debug,
    "eval": eval,
}


class _ServerState:
    """Mutable server state, initialized lazily at server startup."""

    def __init__(self) -> None:
        self.lock: asyncio.Lock | None = None
        self.baseline_env: dict[str, str] | None = None

    def init(self) -> None:
        """Must be called inside a running event loop at server startup."""
        if self.lock is not None:
            return
        self.lock = asyncio.Lock()
        self.baseline_env = os.environ.copy()


_state = _ServerState()


DEFAULT_PRELOAD_MODULES = [
    # Network/async - slowest to load
    "pysignalr.client",
    "socketio",
    "httpx",
    # Validation/serialization
    "pydantic",
    "pydantic_function_models",
    # CLI/UI
    "click",
    "rich",
]


def preload_modules() -> None:
    """Pre-load modules registered by all uipath packages."""
    console.info("Pre-loading modules...")
    start = time.perf_counter()

    modules_to_load: set[str] = set(DEFAULT_PRELOAD_MODULES)

    for ep in entry_points(group="uipath.preload"):
        try:
            get_modules = ep.load()
            modules_to_load.update(get_modules())
        except Exception as e:
            console.warning(f"Failed to load entry point {ep.name}: {e}")

    for module_name in modules_to_load:
        if module_name in sys.modules:
            continue
        if find_spec(module_name) is None:
            continue
        try:
            importlib.import_module(module_name)
            console.success(f"Pre-loaded module: {module_name}")
        except ImportError as e:
            console.warning(f"Failed to load {module_name}: {e}")

    elapsed = time.perf_counter() - start
    console.success(f"Modules pre-loaded in {elapsed:.2f}s")


def get_field(message: dict[str, Any], *keys: str) -> Any:
    """Get a field from message, trying multiple key variations."""
    for key in keys:
        if key in message:
            return message[key]
    return None


def parse_args(args: str | list[str] | None) -> list[str]:
    """Parse args into a list of strings."""
    if args is None:
        return []
    if isinstance(args, list):
        return args
    if isinstance(args, str):
        return shlex.split(args)
    return []


class _CurrentJob:
    """The single in-flight job (jobs are serialized by ``_state.lock``), so a
    ``CancelJob`` RPC — or a host-cancelled ``StartJob`` — can signal a
    cooperative stop the runtime may poll via :func:`get_current_cancellation`.
    """

    def __init__(self) -> None:
        self.job_key: str | None = None
        self.cancel_event: threading.Event | None = None

    def begin(self, job_key: str) -> threading.Event:
        event = threading.Event()
        self.job_key = job_key
        self.cancel_event = event
        return event

    def end(self, job_key: str) -> None:
        if self.job_key == job_key:
            self.job_key = None
            self.cancel_event = None

    def cancel(self, job_key: str) -> bool:
        if self.job_key == job_key and self.cancel_event is not None:
            self.cancel_event.set()
            return True
        return False


_current_job = _CurrentJob()


def get_current_cancellation() -> threading.Event | None:
    """Cooperative-cancel signal for the currently running job, or ``None``.

    A runtime (run/debug/eval, or the agent) may poll ``.is_set()`` to stop
    early. Thread-safe (a ``threading.Event``); jobs are serialized, so there is
    at most one at a time. NOTE: whether a job actually observes this is up to
    the runtime/agent — cancellation is cooperative and best-effort.
    """
    return _current_job.cancel_event


def _runtime_version() -> str:
    try:
        return version("uipath")
    except PackageNotFoundError:
        return "unknown"


async def _run_command_isolated(
    cmd: Any,
    args: list[str],
    env_vars: dict[str, str],
    working_dir: str | None,
    cancel_event: threading.Event,
) -> dict[str, Any]:
    """Run one command with per-job env/cwd isolation; return ``{ExitCode, Error}``.

    Serialized by ``_state.lock``, with ``os.environ`` reset to the server
    baseline + request vars and cwd swapped/restored around the run. The rich
    result is written off-channel (``output.json``); IPC carries only the exit
    code and error.
    """
    if _state.lock is None or _state.baseline_env is None:
        raise RuntimeError("Server state not initialized")

    async with _state.lock:
        original_cwd = os.getcwd()
        try:
            # Start from server baseline + request env vars only, so nothing from
            # a previous job leaks through.
            os.environ.clear()
            os.environ.update(_state.baseline_env)
            if isinstance(env_vars, dict):
                os.environ.update(env_vars)

            if working_dir and isinstance(working_dir, str):
                try:
                    os.chdir(working_dir)
                except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
                    return {
                        "ExitCode": 1,
                        "Error": f"Cannot change to working directory: {e}",
                    }

            job_task = asyncio.ensure_future(
                asyncio.to_thread(cmd.main, args, standalone_mode=False)
            )
            try:
                await asyncio.shield(job_task)
                return {"ExitCode": 0, "Error": None}
            except asyncio.CancelledError:
                # The host cancelled the call. The worker thread can't be
                # force-killed, so signal cooperative cancellation and wait for it
                # to unwind before restoring env/cwd, then propagate.
                cancel_event.set()
                try:
                    await job_task
                except BaseException:
                    pass
                raise
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 1
            return {
                "ExitCode": exit_code,
                "Error": None if exit_code == 0 else f"Exit code: {exit_code}",
            }
        except Exception as e:  # report any job failure as a result, not a fault
            return {"ExitCode": 1, "Error": str(e)}
        finally:
            # Restore to server baseline.
            try:
                os.chdir(original_cwd)
            except OSError:
                pass
            os.environ.clear()
            os.environ.update(_state.baseline_env)


class IPythonRuntimeServer(ABC):
    """Contract the .NET job executor calls over uipath-ipc.

    ``__name__`` is the wire endpoint (matching the .NET ``IPythonRuntimeServer``);
    DTOs cross as PascalCase dicts.
    """

    @abstractmethod
    async def Ping(self) -> dict[str, Any]:
        """Readiness probe → ``{Status, RuntimeVersion}`` (replaces the push-ACK)."""

    @ipc_cancellable
    @abstractmethod
    async def StartJob(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a job (``request`` = PythonRunRequest) → ``{ExitCode, Error}``.

        ``@ipc_cancellable``: the .NET counterpart's trailing ``CancellationToken``
        lets the client cancel the call, which surfaces here as cooperative cancel.
        """

    @abstractmethod
    async def CancelJob(self, jobKey: str) -> bool:
        """Signal a cooperative cancel for ``jobKey``; ``True`` if it was in flight."""


class PythonRuntimeService:
    """``IPythonRuntimeServer`` implementation backed by run/debug/eval."""

    async def Ping(self) -> dict[str, Any]:
        return {"Status": "ready", "RuntimeVersion": _runtime_version()}

    async def StartJob(self, request: dict[str, Any]) -> dict[str, Any]:
        job_key = str(get_field(request, "JobKey", "jobKey") or "")

        command_name = get_field(request, "Command", "command")
        if not isinstance(command_name, str):
            return {"ExitCode": 1, "Error": "Missing or invalid field: 'Command'"}

        cmd = COMMANDS.get(command_name)
        if cmd is None:
            return {"ExitCode": 1, "Error": f"Unknown command: {command_name}"}

        args = parse_args(get_field(request, "Args", "args"))
        env_vars = get_field(request, "EnvironmentVariables", "environmentVariables") or {}
        working_dir = get_field(request, "WorkingDirectory", "workingDirectory")

        console.info(f"Starting job {job_key}: {command_name} {args}")

        cancel_event = _current_job.begin(job_key)
        try:
            return await _run_command_isolated(
                cmd, args, env_vars, working_dir, cancel_event
            )
        finally:
            _current_job.end(job_key)

    async def CancelJob(self, jobKey: str) -> bool:
        signalled = _current_job.cancel(str(jobKey))
        console.info(
            f"CancelJob {jobKey}: "
            + ("signalled cooperative stop" if signalled else "no matching in-flight job")
        )
        return signalled


async def start_ipc_server(pipe_name: str) -> None:
    """Serve the Python runtime over a uipath-ipc named pipe until it is closed."""
    _state.init()
    server = IpcServer(
        transport=NamedPipeServerTransport(pipe_name),
        services={IPythonRuntimeServer: PythonRuntimeService()},
        request_timeout=None,  # jobs are long-running; no server-side timeout
    )
    console.success(f"IPC server listening on pipe '{pipe_name}'")
    async with server:
        await server.serve_forever()


@click.command()
@click.option(
    "--pipe-name",
    type=str,
    required=True,
    help="Named-pipe name to serve the runtime over uipath-ipc. On Linux this is "
    "a $TMPDIR/CoreFxPipe_<name> Unix socket; on Windows a Win32 named pipe.",
)
@track_command("server")
def server(pipe_name: str) -> None:
    """Serve the runtime over uipath-ipc.

    Hosts IPythonRuntimeServer (Ping / StartJob / CancelJob) on the named pipe and
    forwards StartJob to run/debug/eval; the .NET job executor connects as the
    client.
    """
    preload_modules()
    _run_ipc_server(pipe_name)


def _run_ipc_server(pipe_name: str) -> None:
    """Run the IPC server, on a Proactor event loop when on Windows.

    Windows named pipes require the Proactor loop (the Selector loop can't do pipe
    I/O). Proactor is the default since Python 3.8, but we build it explicitly
    rather than trust the ambient policy, which another library in the process
    (e.g. socketio) could have flipped to Selector.
    """
    try:
        if IS_WINDOWS:
            loop = asyncio.ProactorEventLoop()  # type: ignore[attr-defined]
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(start_ipc_server(pipe_name))
            finally:
                loop.close()
        else:
            asyncio.run(start_ipc_server(pipe_name))
    except KeyboardInterrupt:
        console.info("Shutting down")
