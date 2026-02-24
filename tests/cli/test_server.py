import asyncio
import json
import os
import threading
import time
from typing import Any

import aiohttp
import pytest

from uipath._cli.cli_server import start_tcp_server


def create_uipath_json(script_path: str, entrypoint_name: str = "main"):
    """Helper to create uipath.json with functions."""
    return {"functions": {entrypoint_name: f"{script_path}:main"}}


async def start_job(
    port: int, job_key: str, command: str, args: list[str]
) -> dict[str, Any]:
    """Start a job on the server."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"http://127.0.0.1:{port}/jobs/{job_key}/start",
            json={"command": command, "args": args},
        ) as response:
            return await response.json()


async def start_job_with_env(
    port: int,
    job_key: str,
    command: str,
    args: list[str],
    env_vars: dict[str, str],
) -> dict[str, Any]:
    """Start a job on the server with environment variables."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"http://127.0.0.1:{port}/jobs/{job_key}/start",
            json={
                "command": command,
                "args": args,
                "environmentVariables": env_vars,
            },
        ) as response:
            return await response.json()


class TestServer:
    @pytest.fixture
    def server_port(self):
        """Use a random available port for testing."""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @pytest.fixture
    def server(self, server_port):
        """Start the server in a background thread."""

        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(start_tcp_server("127.0.0.1", server_port))
            except asyncio.CancelledError:
                pass
            finally:
                loop.close()

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.5)

        yield server_port

    @pytest.fixture
    def simple_script(self) -> str:
        return """
from dataclasses import dataclass

@dataclass
class Input:
    message: str
    repeat: int = 1

def main(input: Input) -> str:
    return (input.message + " ") * input.repeat
"""

    def test_start_job_success(self, server, temp_dir, simple_script):
        """Test starting a job through the server."""
        port = server
        job_key = "test-job-123"

        with pytest.MonkeyPatch().context() as mp:
            mp.chdir(temp_dir)

            script_file = "entrypoint.py"
            script_path = os.path.join(temp_dir, script_file)
            with open(script_path, "w") as f:
                f.write(simple_script)

            with open(os.path.join(temp_dir, "uipath.json"), "w") as f:
                json.dump(create_uipath_json(script_file), f)

            input_file = os.path.join(temp_dir, "input.json")
            with open(input_file, "w") as f:
                json.dump({"message": "Hello", "repeat": 3}, f)

            output_file = os.path.join(temp_dir, "output.json")

            response = asyncio.run(
                start_job(
                    port,
                    job_key,
                    "run",
                    ["main", "--input-file", input_file, "--output-file", output_file],
                )
            )

            assert response["success"] is True
            assert response["job_key"] == job_key
            assert os.path.exists(output_file)

            with open(output_file, "r") as f:
                output = f.read()
                assert "Hello" in output

    def test_start_job_unknown_command(self, server):
        """Test starting a job with unknown command."""
        port = server

        response = asyncio.run(start_job(port, "job-123", "unknown_command", []))

        assert response["success"] is False
        assert "Unknown command" in response["error"]

    def test_start_job_missing_command(self, server):
        """Test starting a job without command field."""
        port = server

        async def send_invalid():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://127.0.0.1:{port}/jobs/job-123/start",
                    json={"args": ["some", "args"]},
                ) as response:
                    return await response.json()

        response = asyncio.run(send_invalid())

        assert response["success"] is False
        assert "command" in response["error"]

    def test_start_job_invalid_json(self, server):
        """Test starting a job with invalid JSON."""
        port = server

        async def send_invalid():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://127.0.0.1:{port}/jobs/job-123/start",
                    data="not valid json",
                    headers={"Content-Type": "application/json"},
                ) as response:
                    return await response.json()

        response = asyncio.run(send_invalid())

        assert response["success"] is False
        assert "Invalid JSON" in response["error"]

    def test_rejects_invalid_host_header(self, server):
        """Test that requests with non-localhost Host header are rejected (DNS rebinding protection)."""
        port = server

        async def send_with_host(host: str):
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{port}/health",
                    headers={"Host": host},
                ) as response:
                    return response.status, await response.json()

        # Attacker-controlled domain should be rejected
        status, body = asyncio.run(send_with_host("attacker.example.com"))
        assert status == 403
        assert "Forbidden" in body["error"]

        # Attacker domain with port should also be rejected
        status, body = asyncio.run(send_with_host(f"evil.com:{port}"))
        assert status == 403
        assert "Forbidden" in body["error"]

    def test_allows_localhost_host_header(self, server):
        """Test that requests with valid localhost Host headers are accepted."""
        port = server

        async def send_with_host(host: str):
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{port}/health",
                    headers={"Host": host},
                ) as response:
                    return response.status, await response.text()

        # localhost variants should all be accepted
        for host in [
            "127.0.0.1",
            f"127.0.0.1:{port}",
            "localhost",
            f"localhost:{port}",
            "[::1]",
            f"[::1]:{port}",
            "LOCALHOST",
            f"LOCALHOST:{port}",
            "LocalHost",
            "127.0.0.1.",
            f"localhost.:{port}",
        ]:
            status, body = asyncio.run(send_with_host(host))
            assert status == 200, f"Host '{host}' should be allowed but got {status}"
            assert body == "OK"


class TestServerEnvIsolation:
    """Test that environment variables are isolated between sequential server requests."""

    @pytest.fixture
    def server_port(self):
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @pytest.fixture
    def env_snapshots(self):
        return []

    @pytest.fixture
    def server_with_spy(self, server_port, env_snapshots):
        """Start server with a spy command that captures os.environ."""
        import click

        from uipath._cli import cli_server

        @click.command()
        def spy_cmd():
            env_snapshots.append(dict(os.environ))

        original_commands = cli_server.COMMANDS.copy()
        cli_server.COMMANDS["spy"] = spy_cmd

        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(start_tcp_server("127.0.0.1", server_port))
            except asyncio.CancelledError:
                pass
            finally:
                loop.close()

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        time.sleep(0.5)

        yield server_port

        cli_server.COMMANDS.clear()
        cli_server.COMMANDS.update(original_commands)

    def test_env_vars_do_not_leak_between_requests(
        self, server_with_spy, env_snapshots
    ):
        """Env vars from request 1 must not be visible in request 2."""
        port = server_with_spy

        # Request 1: set TEST_VAR_A
        asyncio.run(
            start_job_with_env(
                port,
                "job-1",
                "spy",
                [],
                {"TEST_VAR_A": "value_a"},
            )
        )

        # Request 2: set TEST_VAR_B (but NOT TEST_VAR_A)
        asyncio.run(
            start_job_with_env(
                port,
                "job-2",
                "spy",
                [],
                {"TEST_VAR_B": "value_b"},
            )
        )

        assert len(env_snapshots) == 2

        env_run1 = env_snapshots[0]
        env_run2 = env_snapshots[1]

        # Run 1 should have TEST_VAR_A
        assert env_run1["TEST_VAR_A"] == "value_a"
        assert "TEST_VAR_B" not in env_run1

        # Run 2 should have TEST_VAR_B but NOT TEST_VAR_A
        assert env_run2["TEST_VAR_B"] == "value_b"
        assert "TEST_VAR_A" not in env_run2

    def test_server_baseline_env_preserved(self, server_with_spy, env_snapshots):
        """Server baseline env vars (like PATH) should be available during command execution."""
        from uipath._cli import cli_server

        port = server_with_spy

        asyncio.run(
            start_job_with_env(
                port,
                "job-1",
                "spy",
                [],
                {"CUSTOM_VAR": "custom_value"},
            )
        )

        assert len(env_snapshots) == 1
        env_run = env_snapshots[0]

        # Baseline is captured at server start, not import time
        baseline = cli_server._state.baseline_env
        assert baseline is not None

        # Baseline env vars should be present
        assert env_run.get("PATH") == baseline.get("PATH")

        # Request env var should override/add
        assert env_run["CUSTOM_VAR"] == "custom_value"

    def test_env_restored_after_request(self, server_with_spy):
        """os.environ should be restored to baseline after each request."""
        from uipath._cli import cli_server

        port = server_with_spy

        asyncio.run(
            start_job_with_env(
                port,
                "job-1",
                "spy",
                [],
                {"SHOULD_NOT_PERSIST": "temporary"},
            )
        )

        baseline = cli_server._state.baseline_env
        assert baseline is not None

        # After the request, os.environ should match baseline
        assert "SHOULD_NOT_PERSIST" not in os.environ
        for key in baseline:
            assert os.environ.get(key) == baseline[key]
