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

from ._utils._console import ConsoleLogger
from .cli_debug import debug
from .cli_eval import eval
from .cli_run import run

console = ConsoleLogger()

SOCKET_ENV_VAR = "UIPATH_SERVER_SOCKET"
DEFAULT_SOCKET_PATH = "/tmp/uipath-server.sock"
DEFAULT_PORT = 8765

IS_WINDOWS = sys.platform == "win32"

COMMANDS = {
    "run": run,
    "debug": debug,
    "eval": eval,
}

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


def generate_socket_path() -> str:
    """Generate a unique socket path for the server to listen on."""
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
    """Handle POST /jobs/{job_key}/start endpoint."""
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

    args_raw = get_field(message, "args", "Args")
    args = parse_args(args_raw)

    env_vars = get_field(message, "environmentVariables", "EnvironmentVariables") or {}
    working_dir = get_field(message, "workingDirectory", "WorkingDirectory")

    console.info(f"Starting job {job_key}: {command_name} {args}")

    cmd = COMMANDS.get(command_name)
    if cmd is None:
        return web.json_response(
            {"success": False, "error": f"Unknown command: {command_name}"},
            status=400,
        )

    # Save original state
    original_cwd = os.getcwd()
    original_env = os.environ.copy()

    console.info(f"Original cwd: {original_cwd}")
    console.info(f"Requested working_dir: {working_dir}")

    try:
        if isinstance(env_vars, dict):
            os.environ.update(env_vars)

        if working_dir and isinstance(working_dir, str):
            os.chdir(working_dir)

        result = await asyncio.to_thread(cmd.main, args, standalone_mode=False)

        return web.json_response(
            {
                "success": True,
                "job_key": job_key,
                "result": result,
            }
        )
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        return web.json_response(
            {
                "success": exit_code == 0,
                "job_key": job_key,
                "error": None if exit_code == 0 else f"Exit code: {exit_code}",
            }
        )
    except Exception as e:
        return web.json_response(
            {"success": False, "job_key": job_key, "error": str(e)},
            status=500,
        )
    finally:
        # Restore original state
        os.chdir(original_cwd)
        os.environ.clear()
        os.environ.update(original_env)


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


async def start_unix_server(ack_socket_path: str) -> None:
    """Start Unix domain socket HTTP server."""
    server_socket_path = generate_socket_path()

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


@click.command()
@click.option(
    "--socket",
    type=str,
    default=None,
    help=f"Unix socket path to send ready ack to (default: ${SOCKET_ENV_VAR} or {DEFAULT_SOCKET_PATH})",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help=f"TCP port, used on Windows or when --tcp flag is set (default: {DEFAULT_PORT})",
)
@click.option(
    "--tcp",
    is_flag=True,
    help="Force TCP mode even on Unix systems",
)
def server(socket: str | None, port: int | None, tcp: bool) -> None:
    """Start an HTTP server that forwards commands to run/debug/eval.

    Creates its own socket to listen on and sends an ack to --socket with:
    {"status": "ready", "socket": "/path/to/server.sock"}

    Endpoint: POST /jobs/{job_key}/start
    Body: {"command": "run", "args": "agent.json '{}'", "environmentVariables": {}, "workingDirectory": "/path"}

    Endpoint: GET /health
    """
    use_tcp = IS_WINDOWS or tcp

    preload_modules()

    try:
        if use_tcp:
            asyncio.run(start_tcp_server("127.0.0.1", port or DEFAULT_PORT))
        else:
            ack_socket_path = (
                socket or os.environ.get(SOCKET_ENV_VAR) or DEFAULT_SOCKET_PATH
            )
            asyncio.run(start_unix_server(ack_socket_path))
    except KeyboardInterrupt:
        console.info("Shutting down")
