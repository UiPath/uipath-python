"""Tests for the uipath-ipc runtime server channel.

The server hosts ``IPythonRuntimeServer`` (RunJob / StopJob) on a named pipe
alongside the HTTP channel when ``--ipc-pipe`` names one (see
``test_server_transport.py`` for the channel composition). Mirrors
``test_server.py`` (the HTTP path) but drives the pipe with a Python
``uipath-ipc`` client.

Requires ``uipath-ipc`` to be installed. ``RunJob`` success runs the real
runtime (like ``test_server.test_start_job_success``); the rest exercise the IPC
wiring and env isolation without it.
"""

import asyncio
import json
import os
import sys
import threading
import time
import types
from typing import Any, Awaitable, Callable

import click
import pytest
from uipath_ipc import (
    IpcClient,
    IpcServer,
    Message,
    NamedPipeClientTransport,
    NamedPipeServerTransport,
)

from uipath._cli import _server_core
from uipath._cli.cli_server import (
    IPythonRuntimeServer,
    PythonRuntimeService,
    PythonServerRunJobResult,
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
    _wait_until_ready(pipe_name)


async def _with_proxy(pipe_name: str, fn: Callable[[Any], Awaitable[Any]]) -> Any:
    """Connect a uipath-ipc client to the pipe, run ``fn(proxy)``, then close."""
    client = IpcClient(transport=NamedPipeClientTransport(pipe_name))
    try:
        # get_proxy is by-contract; the abstract interface is exactly what it wants.
        proxy = client.get_proxy(IPythonRuntimeServer)  # type: ignore[type-abstract]
        return await fn(proxy)
    finally:
        await client.aclose()


def _wait_until_ready(pipe_name: str, timeout: float = 10.0) -> None:
    """Poll the pipe until the IPC server answers, instead of a fixed sleep.

    A fixed ``sleep`` races the server's startup under load; this connects a real
    client and calls ``Register`` until it succeeds (or times out).
    """
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            asyncio.run(_with_proxy(pipe_name, lambda p: p.Register()))
            return
        except Exception as e:  # server not accepting connections yet
            last_err = e
            time.sleep(0.05)
    raise TimeoutError(
        f"IPC server on pipe {pipe_name!r} not ready within {timeout}s: {last_err}"
    )


def create_uipath_json(
    script_path: str, entrypoint_name: str = "main"
) -> dict[str, Any]:
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


def test_start_ipc_server_fails_fast_without_uipath_ipc(monkeypatch):
    """--ipc-pipe with uipath-ipc absent must fail loudly, not silently no-op."""
    monkeypatch.setitem(sys.modules, "uipath_ipc", None)
    coro = start_ipc_server(_unique_pipe())
    with pytest.raises(RuntimeError, match="uipath-ipc"):
        asyncio.run(coro)


class TestIpcServer:
    @pytest.fixture
    def pipe(self):
        pipe_name = _unique_pipe()
        _serve_in_background(pipe_name)
        # Daemon thread; the server blocks in serve_forever and is torn down when
        # the process exits (mirrors test_server.py's background HTTP server).
        yield pipe_name

    def test_run_job_success(self, pipe, temp_dir):
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
        result = asyncio.run(_with_proxy(pipe, lambda p: p.RunJob(request)))

        assert result.ExitCode == 0
        assert result.Error is None
        assert os.path.exists(output_file)
        with open(output_file, "r") as f:
            assert "Hello" in f.read()

    def test_run_job_unknown_command(self, pipe):
        request = {"JobKey": "job-1", "Command": "does_not_exist"}
        result = asyncio.run(_with_proxy(pipe, lambda p: p.RunJob(request)))
        assert result.ExitCode != 0
        assert "Unknown command" in (result.Error or "")

    def test_run_job_missing_command(self, pipe):
        """Absent/empty Command is rejected before the job core is touched."""
        result = asyncio.run(_with_proxy(pipe, lambda p: p.RunJob({"JobKey": "job-1"})))
        assert result.ExitCode != 0
        assert "Command" in (result.Error or "")

    def test_run_job_accepts_resume_version(self, pipe):
        request = {
            "JobKey": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
            "ResumeVersion": 4,
            "Command": "does_not_exist",
        }
        result = asyncio.run(_with_proxy(pipe, lambda p: p.RunJob(request)))

        assert "Unknown command" in (result.Error or "")

    def test_stop_job_accepts_resume_version_and_force_stop(self, pipe):
        request = {
            "JobKey": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
            "ResumeVersion": 2,
            "ForceStop": True,
        }
        result = asyncio.run(_with_proxy(pipe, lambda p: p.StopJob(request)))

        assert result is True

    def test_stop_job_returns_true(self, pipe):
        """StopJob is a no-op stub today, but must ack (bool) so the call is awaitable."""
        result = asyncio.run(
            _with_proxy(
                pipe, lambda p: p.StopJob({"JobKey": "job-1", "ForceStop": True})
            )
        )
        assert result is True


class TestIpcServerEnvIsolation:
    """Env vars must not leak between sequential jobs (as on the HTTP path)."""

    @pytest.fixture
    def pipe_with_spy(self):
        env_snapshots: list[dict[str, str]] = []

        @click.command()
        def spy_cmd() -> None:
            env_snapshots.append(dict(os.environ))

        original = _server_core.COMMANDS.copy()
        _server_core.COMMANDS["spy"] = spy_cmd

        pipe_name = _unique_pipe()
        _serve_in_background(pipe_name)
        try:
            yield pipe_name, env_snapshots
        finally:
            _server_core.COMMANDS.clear()
            _server_core.COMMANDS.update(original)

    def test_env_vars_do_not_leak_between_jobs(self, pipe_with_spy):
        pipe_name, env_snapshots = pipe_with_spy

        async def run_two(proxy: Any) -> None:
            await proxy.RunJob(
                {
                    "JobKey": "job-1",
                    "Command": "spy",
                    "EnvironmentVariables": {"TEST_VAR_A": "a"},
                }
            )
            await proxy.RunJob(
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


class TestIpcContractFieldTransit:
    @staticmethod
    def _serve_spy(pipe_name: str, service: IPythonRuntimeServer) -> None:
        def run_server() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def main() -> None:
                server = IpcServer(
                    transport=NamedPipeServerTransport(pipe_name),
                    services={IPythonRuntimeServer: service},
                    request_timeout=None,
                )
                async with server:
                    await server.serve_forever()

            try:
                loop.run_until_complete(main())
            except asyncio.CancelledError:
                pass
            finally:
                loop.close()

        threading.Thread(target=run_server, daemon=True).start()
        _wait_until_ready(pipe_name)

    def test_all_wire_fields_arrive_intact(self):
        received: list[Any] = []

        class SpyService(IPythonRuntimeServer):
            async def Register(self, message: Any) -> bool:
                return True

            async def RunJob(self, request: Any) -> PythonServerRunJobResult:
                received.append(request)
                return PythonServerRunJobResult(ExitCode=0)

            async def StopJob(self, request: Any) -> bool:
                received.append(request)
                return True

        pipe = _unique_pipe()
        self._serve_spy(pipe, SpyService())
        received.clear()  # drop the readiness probe's StopJob

        job_key = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"

        async def drive(proxy: Any) -> None:
            await proxy.RunJob(
                {
                    "JobKey": job_key,
                    "ResumeVersion": 5,
                    "Command": "run",
                    "Args": "main --input-file in.json",
                    "WorkingDirectory": "/tmp/wd",
                    "EnvironmentVariables": {"A": "1"},
                }
            )
            await proxy.StopJob(
                {"JobKey": job_key, "ResumeVersion": 5, "ForceStop": True}
            )

        asyncio.run(_with_proxy(pipe, drive))

        run_request, stop_request = received
        assert run_request.JobKey == job_key
        assert run_request.ResumeVersion == 5
        assert run_request.Command == "run"
        assert run_request.Args == "main --input-file in.json"
        assert run_request.WorkingDirectory == "/tmp/wd"
        assert run_request.EnvironmentVariables == {"A": "1"}

        assert stop_request.JobKey == job_key
        assert stop_request.ResumeVersion == 5
        assert stop_request.ForceStop is True


class TestPooledLogSink:
    """``Register`` wires the runtime's process-global log sink to the caller's callback.

    This is the pooled path: the handler dials in and hosts an ``IIpcLogSink`` callback; the server
    grabs it off the injected ``Message`` and points the runtime's sink at it, so a pooled job's logs
    reach back over the same pipe. The runtime side is exercised in uipath-runtime's own tests; here
    we lock in the seam (get_callback → set_pooled_log_sink → forward on the loop).
    """

    @staticmethod
    def _fake_runtime_jobapi(monkeypatch: Any) -> dict[str, Any]:
        """Install a stand-in ``uipath.runtime.jobapi`` and record what the server wires into it."""
        captured: dict[str, Any] = {}

        class IIpcLogSink:  # matches the contract the server asks get_callback for
            pass

        def set_pooled_log_sink(sink: Any) -> None:
            captured["sink"] = sink

        module = types.ModuleType("uipath.runtime.jobapi")
        module.IIpcLogSink = IIpcLogSink  # type: ignore[attr-defined]
        module.set_pooled_log_sink = set_pooled_log_sink  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "uipath.runtime.jobapi", module)
        captured["IIpcLogSink"] = IIpcLogSink
        return captured

    def test_register_forwards_logs_to_the_caller_callback(self, monkeypatch):
        captured = self._fake_runtime_jobapi(monkeypatch)
        sent: list[tuple[str, Any]] = []

        class _Callback:
            async def SendLog(self, job_id: str, log: Any) -> None:
                sent.append((job_id, log))

        class _Client:
            def __init__(self) -> None:
                self.asked_for: Any = None

            def get_callback(self, contract: Any) -> Any:
                self.asked_for = contract
                return _Callback()

        client = _Client()

        async def scenario() -> None:
            ok = await PythonRuntimeService().Register(Message(client=client))
            assert ok is True
            # It asked the caller for exactly the IIpcLogSink callback...
            assert client.asked_for is captured["IIpcLogSink"]
            # ...and registered a forwarder. Driving it (as the runtime would, off a worker thread)
            # schedules SendLog on this loop, tagged with the job id.
            sink = captured["sink"]
            log = {"Message": "hello", "LogLevel": 2}
            sink("job-key-42", log)
            await asyncio.sleep(0.05)
            assert sent == [("job-key-42", log)]

        asyncio.run(scenario())

    def test_register_is_graceful_when_runtime_lacks_pooled_sink(self, monkeypatch):
        # An older uipath-runtime has no jobapi module: importing it raises, and Register must still
        # succeed (the job simply keeps its file+watcher log path).
        monkeypatch.setitem(sys.modules, "uipath.runtime.jobapi", None)

        class _Client:
            def get_callback(
                self, contract: Any
            ) -> Any:  # pragma: no cover - never reached
                raise AssertionError(
                    "must not reach get_callback without the runtime API"
                )

        async def scenario() -> None:
            assert (
                await PythonRuntimeService().Register(Message(client=_Client())) is True
            )

        asyncio.run(scenario())

    def test_register_without_a_caller_handle_is_a_noop(self, monkeypatch):
        # A Message with no client (defensive; real dispatch always injects one) wires nothing.
        captured = self._fake_runtime_jobapi(monkeypatch)

        async def scenario() -> None:
            assert await PythonRuntimeService().Register(Message()) is True

        asyncio.run(scenario())
        assert "sink" not in captured
