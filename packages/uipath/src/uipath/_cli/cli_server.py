import asyncio
import importlib
import json
import os
import shlex
import sys
import tempfile
import time
from importlib.metadata import entry_points
from importlib.util import find_spec
from typing import Any

import click
from aiohttp import ClientSession, UnixConnector, web

from ._telemetry import track_command
from ._utils._console import ConsoleLogger
from .cli_debug import debug
from .cli_eval import eval
from .cli_run import run
from .cli_server_ipc import (
    IPythonRuntimeServer,
    PythonRunRequest,
    PythonRunResult,
    PythonRuntimeService,
    start_ipc_server,
)

__all__ = [
    "server",
    "IPythonRuntimeServer",
    "PythonRunRequest",
    "PythonRunResult",
    "PythonRuntimeService",
    "start_ipc_server",
]

console = ConsoleLogger()

IS_WINDOWS = sys.platform == "win32"

SOCKET_ENV_VAR = "UIPATH_SERVER_SOCKET"
DEFAULT_SOCKET_PATH = "/tmp/uipath-server.sock"
DEFAULT_PORT = 8765

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
        try:
            # find_spec raises ModuleNotFoundError when a parent package is missing
            if find_spec(module_name) is None:
                continue
            importlib.import_module(module_name)
            console.success(f"Pre-loaded module: {module_name}")
        except ImportError as e:
            console.warning(f"Failed to load {module_name}: {e}")

    elapsed = time.perf_counter() - start
    console.success(f"Modules pre-loaded in {elapsed:.2f}s")


def generate_socket_path() -> str:
    """Generate a unique socket path for the HTTP server to listen on."""
    return os.path.join(tempfile.gettempdir(), f"uipath-server-{os.getpid()}.sock")


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


async def _run_command_isolated(
    cmd: Any,
    args: list[str],
    env_vars: dict[str, str],
    working_dir: str | None,
) -> dict[str, Any]:
    """Run one command with per-job env/cwd isolation (the shared job core)."""
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
                        "Result": None,
                        "Unexpected": False,
                    }

            result_value = await asyncio.to_thread(
                cmd.main, args, standalone_mode=False
            )
            return {
                "ExitCode": 0,
                "Error": None,
                "Result": result_value,
                "Unexpected": False,
            }
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 1
            return {
                "ExitCode": exit_code,
                "Error": None if exit_code == 0 else f"Exit code: {exit_code}",
                "Result": None,
                "Unexpected": False,
            }
        except Exception as e:  # report any job failure as a result, not a fault
            return {"ExitCode": 1, "Error": str(e), "Result": None, "Unexpected": True}
        finally:
            # Restore to server baseline.
            try:
                os.chdir(original_cwd)
            except OSError:
                pass
            os.environ.clear()
            os.environ.update(_state.baseline_env)


# --------------------------------------------------------------------------- #
# HTTP transport (default) — aiohttp over a Unix socket / TCP, with ready-ACK  #
# --------------------------------------------------------------------------- #


async def send_ack(ack_socket_path: str, server_socket_path: str) -> None:
    """Send acknowledgment via HTTP POST to the ack socket."""
    ack_message: dict[str, str] = {
        "status": "ready",
        "socket": server_socket_path,
    }

    conn = UnixConnector(path=ack_socket_path)
    try:
        async with ClientSession(connector=conn) as session:
            async with session.post(
                "http://localhost/api/python/ack",  # placeholder URL for Unix socket
                json=ack_message,
            ) as response:
                if response.status == 200:
                    console.success(f"Sent ack to {ack_socket_path}")
                else:
                    console.error(f"Ack failed with status {response.status}")
                    raise RuntimeError(f"Ack failed: {response.status}")
    except Exception as e:
        console.error(f"Failed to send ack to {ack_socket_path}: {e}")
        raise


async def handle_health(request: web.Request) -> web.Response:
    """Handle GET /health endpoint."""
    return web.Response(text="OK", status=200)


async def handle_start(request: web.Request) -> web.Response:
    """Handle POST /jobs/{job_key}/start — runs a job via the shared core."""
    job_key = request.match_info.get("job_key")
    if not job_key:
        return web.json_response(
            {"success": False, "error": "Missing job_key"},
            status=400,
        )

    try:
        message: dict[str, Any] = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"success": False, "error": "Invalid JSON"},
            status=400,
        )

    command_name = get_field(message, "command", "Command")
    if not isinstance(command_name, str):
        return web.json_response(
            {"success": False, "error": "Missing or invalid field: 'command'"},
            status=400,
        )

    args = parse_args(get_field(message, "args", "Args"))
    env_vars = get_field(message, "environmentVariables", "EnvironmentVariables") or {}
    working_dir = get_field(message, "workingDirectory", "WorkingDirectory")

    if env_vars and not isinstance(env_vars, dict):
        return web.json_response(
            {
                "success": False,
                "error": "Invalid field: 'environmentVariables' must be a dict",
            },
            status=400,
        )

    cmd = COMMANDS.get(command_name)
    if cmd is None:
        return web.json_response(
            {"success": False, "error": f"Unknown command: {command_name}"},
            status=400,
        )

    console.info(f"Starting job {job_key}: {command_name} {args}")

    result = await _run_command_isolated(cmd, args, env_vars, working_dir)

    if result["Unexpected"]:
        return web.json_response(
            {"success": False, "job_key": job_key, "error": result["Error"]},
            status=500,
        )
    if result["ExitCode"] == 0:
        return web.json_response(
            {"success": True, "job_key": job_key, "result": result["Result"]}
        )
    return web.json_response(
        {"success": False, "job_key": job_key, "error": result["Error"]}
    )


ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


@web.middleware
async def host_validation_middleware(
    request: web.Request, handler: Any
) -> web.StreamResponse:
    """Validate the Host header to prevent DNS rebinding attacks."""
    host = request.host
    if host:
        host = host.lower()
        # Strip port from bracketed IPv6 (e.g. "[::1]:8765" -> "[::1]")
        if host.startswith("["):
            bracket_end = host.find("]")
            if bracket_end != -1:
                host = host[: bracket_end + 1]
        # Strip port from IPv4/hostname (e.g. "localhost:8765" -> "localhost")
        elif ":" in host:
            host = host.rsplit(":", 1)[0]
        # Strip trailing dot (e.g. "localhost." -> "localhost")
        host = host.rstrip(".")
    if host not in ALLOWED_HOSTS:
        return web.json_response(
            {"error": "Forbidden: invalid Host header"},
            status=403,
        )
    return await handler(request)


def create_app() -> web.Application:
    """Create the aiohttp application."""
    app = web.Application(middlewares=[host_validation_middleware])
    app.router.add_get("/health", handle_health)
    app.router.add_post("/jobs/{job_key}/start", handle_start)
    return app


async def start_unix_server(
    ack_socket_path: str, server_socket_path: str | None = None
) -> None:
    """Start Unix domain socket HTTP server."""
    _state.init()

    server_socket_path = server_socket_path or generate_socket_path()

    if os.path.exists(server_socket_path):
        os.unlink(server_socket_path)

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    try:
        site = web.UnixSite(runner, server_socket_path)
        await site.start()

        console.success(f"Server listening on unix://{server_socket_path}")

        await send_ack(ack_socket_path, server_socket_path)

        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()
        if os.path.exists(server_socket_path):
            os.unlink(server_socket_path)


async def start_tcp_server(host: str, port: int) -> None:
    """Start TCP HTTP server (Windows fallback)."""
    _state.init()

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    try:
        site = web.TCPSite(runner, host, port)
        await site.start()

        console.success(f"Server listening on http://{host}:{port}")

        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()


# The uipath-ipc transport (contract, DTOs, service, ``start_ipc_server``) lives
# in ``cli_server_ipc`` and is served alongside HTTP when ``--server-socket`` is
# given. Older servers served HTTP only; the .NET Handler copes.


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


@click.command()
@click.option(
    "--client-socket",
    type=str,
    default=None,
    help=f"Unix socket to send the ready ACK to (default: ${SOCKET_ENV_VAR} "
    f"or {DEFAULT_SOCKET_PATH}).",
)
@click.option(
    "--server-socket",
    type=str,
    default=None,
    help="Unix socket the HTTP server listens on; its basename is the uipath-ipc "
    "pipe name (default: auto-generated in tmp).",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help=f"TCP port, used on Windows or with --tcp (default: {DEFAULT_PORT}).",
)
@click.option(
    "--tcp",
    is_flag=True,
    help="Force TCP mode even on Unix systems.",
)
@track_command("server")
def server(
    client_socket: str | None,
    server_socket: str | None,
    port: int | None,
    tcp: bool,
) -> None:
    """Serve run/debug/eval over HTTP, plus uipath-ipc when --server-socket is given."""
    preload_modules()
    _run_server(client_socket, server_socket, port, tcp)


async def _serve(
    ack_socket_path: str,
    server_socket: str | None,
    port: int,
    use_tcp: bool,
) -> None:
    """Run the HTTP channel and, when a server socket is given, the IPC channel too."""
    _state.init()

    tasks: list[Any] = []
    if use_tcp:
        tasks.append(start_tcp_server("127.0.0.1", port))
    else:
        tasks.append(start_unix_server(ack_socket_path, server_socket))

    # The IPC pipe name is the HTTP UDS path's basename (directory stripped),
    # identically to the .NET side (Path.GetFileName) — so the named-pipe transport
    # resolves it to a socket distinct from the HTTP UDS and the two never collide.
    if server_socket:
        pipe_name = os.path.basename(server_socket)
        tasks.append(start_ipc_server(pipe_name))
    else:
        console.warning("--server-socket not provided; serving HTTP only (no IPC channel).")

    await asyncio.gather(*tasks)


def _run_server(
    client_socket: str | None,
    server_socket: str | None,
    port: int | None,
    tcp: bool,
) -> None:
    """Drive ``_serve`` on the right event loop for the platform."""
    use_tcp = IS_WINDOWS or tcp
    ack_socket_path = (
        client_socket or os.environ.get(SOCKET_ENV_VAR) or DEFAULT_SOCKET_PATH
    )
    coro = _serve(ack_socket_path, server_socket, port or DEFAULT_PORT, use_tcp)
    try:
        # Windows named pipes need the Proactor loop; build it explicitly since another
        # lib (e.g. socketio) may have flipped the policy to Selector. Gate on the
        # sys.platform literal so mypy narrows ProactorEventLoop (Windows-only) here.
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(coro)
            finally:
                loop.close()
        else:
            asyncio.run(coro)
    except KeyboardInterrupt:
        console.info("Shutting down")
