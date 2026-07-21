"""Tests for the uipath-ipc runtime server channel.

The server always hosts ``IPythonRuntimeServer`` (StartJob / StopJob) on a named
pipe alongside the HTTP channel when a ``--server-socket`` is given (see
``test_server_transport.py`` for the channel composition). Mirrors
``test_server.py`` (the HTTP path) but drives the pipe with a Python
``uipath-ipc`` client.

Requires ``uipath-ipc`` to be installed. ``StartJob`` success runs the real
runtime (like ``test_server.test_start_job_success``); the rest exercise the IPC
wiring and env isolation without it.
"""

import asyncio
import json
import os
import threading
import time
from typing import Any, Awaitable, Callable

import click
import pytest
from uipath_ipc import IpcClient, NamedPipeClientTransport

from uipath._cli import cli_server
from uipath._cli.cli_server import (
    IPythonRuntimeServer,
    start_ipc_server,
)

_pipe_counter = 0


def _unique_pipe() -> str:
    global _pipe_counter
    _pipe_counter += 1
    return f"uipath-ipc-test-{os.getpid()}-{_pipe_counter}"


def _serve_in_background(pipe_name: str) -> None:
    """Run the IPC server on its own event loop in a daemon thread.

    ``asyncio.new_event_loop()`` yields the per-OS default loop — Proactor on
    Windows (required for named pipes), Selector on Linux (CoreFxPipe UDS).
    """

    def run_server() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(start_ipc_server(pipe_name))
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(0.5)


async def _with_proxy(pipe_name: str, fn: Callable[[Any], Awaitable[Any]]) -> Any:
    """Connect a uipath-ipc client to the pipe, run ``fn(proxy)``, then close."""
    client = IpcClient(transport=NamedPipeClientTransport(pipe_name))
    try:
        proxy = client.get_proxy(IPythonRuntimeServer)
        return await fn(proxy)
    finally:
        await client.aclose()


def create_uipath_json(script_path: str, entrypoint_name: str = "main") -> dict:
    return {"functions": {entrypoint_name: f"{script_path}:main"}}


SIMPLE_SCRIPT = """
from dataclasses import dataclass

@dataclass
class Input:
    message: str
    repeat: int = 1

def main(input: Input) -> str:
    return (input.message + " ") * input.repeat
"""


class TestIpcServer:
    @pytest.fixture
    def pipe(self):
        pipe_name = _unique_pipe()
        _serve_in_background(pipe_name)
        # Daemon thread; the server blocks in serve_forever and is torn down when
        # the process exits (mirrors test_server.py's background HTTP server).
        yield pipe_name

    def test_start_job_success(self, pipe, temp_dir):
        """A real 'run' job executes and writes output.json (needs the runtime)."""
        script_file = "entrypoint.py"
        with open(os.path.join(temp_dir, script_file), "w") as f:
            f.write(SIMPLE_SCRIPT)
        with open(os.path.join(temp_dir, "uipath.json"), "w") as f:
            json.dump(create_uipath_json(script_file), f)

        input_file = os.path.join(temp_dir, "input.json")
        with open(input_file, "w") as f:
            json.dump({"message": "Hello", "repeat": 3}, f)
        output_file = os.path.join(temp_dir, "output.json")

        request = {
            "JobKey": "job-123",
            "Command": "run",
            "Args": ["main", "--input-file", input_file, "--output-file", output_file],
            "WorkingDirectory": temp_dir,
            "EnvironmentVariables": {},
        }
        result = asyncio.run(_with_proxy(pipe, lambda p: p.StartJob(request)))

        assert result.ExitCode == 0
        assert result.Error is None
        assert os.path.exists(output_file)
        with open(output_file, "r") as f:
            assert "Hello" in f.read()

    def test_start_job_unknown_command(self, pipe):
        request = {"JobKey": "job-1", "Command": "does_not_exist"}
        result = asyncio.run(_with_proxy(pipe, lambda p: p.StartJob(request)))
        assert result.ExitCode != 0
        assert "Unknown command" in (result.Error or "")


class TestIpcServerEnvIsolation:
    """Env vars must not leak between sequential jobs (as on the HTTP path)."""

    @pytest.fixture
    def pipe_with_spy(self):
        env_snapshots: list[dict[str, str]] = []

        @click.command()
        def spy_cmd() -> None:
            env_snapshots.append(dict(os.environ))

        original = cli_server.COMMANDS.copy()
        cli_server.COMMANDS["spy"] = spy_cmd

        pipe_name = _unique_pipe()
        _serve_in_background(pipe_name)
        try:
            yield pipe_name, env_snapshots
        finally:
            cli_server.COMMANDS.clear()
            cli_server.COMMANDS.update(original)

    def test_env_vars_do_not_leak_between_jobs(self, pipe_with_spy):
        pipe_name, env_snapshots = pipe_with_spy

        async def run_two(proxy: Any) -> None:
            await proxy.StartJob(
                {
                    "JobKey": "job-1",
                    "Command": "spy",
                    "EnvironmentVariables": {"TEST_VAR_A": "a"},
                }
            )
            await proxy.StartJob(
                {
                    "JobKey": "job-2",
                    "Command": "spy",
                    "EnvironmentVariables": {"TEST_VAR_B": "b"},
                }
            )

        asyncio.run(_with_proxy(pipe_name, run_two))

        assert len(env_snapshots) == 2
        run1, run2 = env_snapshots
        assert run1["TEST_VAR_A"] == "a"
        assert "TEST_VAR_B" not in run1
        assert run2["TEST_VAR_B"] == "b"
        assert "TEST_VAR_A" not in run2
