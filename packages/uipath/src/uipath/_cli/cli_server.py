import asyncio
import importlib
import json
import os
import sys
import tempfile
import time
from importlib.metadata import entry_points
from importlib.util import find_spec
from typing import Any

import click
from aiohttp import ClientSession, UnixConnector, web

from ._server_core import (
    COMMANDS,
    _run_command_isolated,
    _state,
    parse_args,
)
from ._telemetry import track_command
from ._utils._console import ConsoleLogger
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
    env_vars = get_field(message, "environmentVariables", "EnvironmentVariables")
    working_dir = get_field(message, "workingDirectory", "WorkingDirectory")

    if env_vars is not None and not isinstance(env_vars, dict):
        return web.json_response(
            {
                "success": False,
                "error": "Invalid field: 'environmentVariables' must be a dict",
            },
            status=400,
        )
    env_vars = env_vars or {}

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
    if result.get("ClientError"):
        # Request-shaped failure (e.g. bad working directory) — 4xx, not 200.
        return web.json_response(
            {"success": False, "job_key": job_key, "error": result["Error"]},
            status=400,
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
# in ``cli_server_ipc`` and is served alongside HTTP when ``--ipc-pipe`` is given.
# Older servers served HTTP only; the .NET Handler copes.


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
    help="Unix socket the HTTP server listens on (default: auto-generated in tmp).",
)
@click.option(
    "--ipc-pipe",
    type=str,
    default=None,
    help="Named pipe for the uipath-ipc channel. IPC is served only when this is "
    "given; omit it for HTTP-only.",
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
    ipc_pipe: str | None,
    port: int | None,
    tcp: bool,
) -> None:
    """Serve run/debug/eval over HTTP, plus uipath-ipc when --ipc-pipe is given."""
    preload_modules()
    _run_server(client_socket, server_socket, ipc_pipe, port, tcp)


async def _serve(
    ack_socket_path: str,
    server_socket: str | None,
    ipc_pipe: str | None,
    port: int,
    use_tcp: bool,
) -> None:
    """Run the HTTP channel, plus the uipath-ipc channel when a pipe name is given."""
    _state.init()

    tasks: list[Any] = []
    if use_tcp:
        tasks.append(start_tcp_server("127.0.0.1", port))
    else:
        tasks.append(start_unix_server(ack_socket_path, server_socket))

    # IPC is opt-in and independent of the HTTP socket: it is served only when an
    # explicit pipe name is given, which both sides agree on out of band (the .NET
    # peer connects to the same name it passed — no derivation from the HTTP socket).
    if ipc_pipe:
        tasks.append(start_ipc_server(ipc_pipe))

    await asyncio.gather(*tasks)


def _run_server(
    client_socket: str | None,
    server_socket: str | None,
    ipc_pipe: str | None,
    port: int | None,
    tcp: bool,
) -> None:
    """Drive ``_serve`` on the right event loop for the platform."""
    use_tcp = IS_WINDOWS or tcp
    ack_socket_path = (
        client_socket or os.environ.get(SOCKET_ENV_VAR) or DEFAULT_SOCKET_PATH
    )
    coro = _serve(
        ack_socket_path, server_socket, ipc_pipe, port or DEFAULT_PORT, use_tcp
    )
    try:
        if sys.platform == "win32":
            with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
                runner.run(coro)
        else:
            asyncio.run(coro)
    except KeyboardInterrupt:
        console.info("Shutting down")
