import asyncio
import socket
import threading
import time
from typing import Any
from urllib.request import urlopen

import aiohttp

from uipath._cli.cli_server import start_tcp_server
from uipath.functions import register_default_runtime_factory


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"server on port {port} did not become healthy") from last_error


def start_cli_server_thread(port: int) -> threading.Thread:
    register_default_runtime_factory()

    def run_server() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(start_tcp_server("127.0.0.1", port))
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    _wait_for_health(port)
    return thread


async def start_job(
    port: int,
    job_key: str,
    command: str,
    args: list[str],
    working_directory: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"command": command, "args": args}
    if working_directory is not None:
        payload["workingDirectory"] = working_directory

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"http://127.0.0.1:{port}/jobs/{job_key}/start",
            json=payload,
        ) as response:
            return await response.json()


async def start_job_with_env(
    port: int,
    job_key: str,
    command: str,
    args: list[str],
    env_vars: dict[str, str],
    working_directory: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "command": command,
        "args": args,
        "environmentVariables": env_vars,
    }
    if working_directory is not None:
        payload["workingDirectory"] = working_directory

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"http://127.0.0.1:{port}/jobs/{job_key}/start",
            json=payload,
        ) as response:
            return await response.json()
