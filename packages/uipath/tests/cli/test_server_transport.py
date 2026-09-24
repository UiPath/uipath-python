"""`uipath server` channel selection.

Without ``--ipc-pipe`` the server speaks HTTP (aiohttp over a Unix socket with a
ready-ACK, or TCP on Windows / ``--tcp``). ``--ipc-pipe`` alone serves only the
uipath-ipc named-pipe channel: no HTTP listener and no ACK. ``--ipc-pipe`` together
with any HTTP option serves both, as callers that pass both still expect.

These tests stub the three channel runners (so ``_serve`` returns at once instead
of serving forever) and assert which channels ``_serve`` starts, how ``_run_server``
resolves its arguments, and how the CLI validates and wires them through.
"""

import asyncio
from typing import Any

import pytest
from click.testing import CliRunner

import uipath._cli._telemetry as _telemetry
from uipath._cli import _server_core, cli_server


def _stub_channels(monkeypatch) -> dict[str, Any]:
    """Stub the three channel runners, the ACK and state init; record what runs.

    ``_state.init`` is stubbed so no event-loop-bound lock leaks between the
    per-test loops ``asyncio.run`` creates.
    """
    calls: dict[str, Any] = {}

    async def _rec_unix(ack_socket_path, server_socket_path=None):
        calls["unix"] = (ack_socket_path, server_socket_path)

    async def _rec_tcp(host, port):
        calls["tcp"] = (host, port)

    async def _rec_ipc(pipe_name):
        calls["ipc"] = pipe_name

    async def _rec_ack(ack_socket_path, server_socket_path):
        calls["ack"] = (ack_socket_path, server_socket_path)

    monkeypatch.setattr(_server_core._state, "init", lambda: None)
    monkeypatch.setattr(cli_server, "start_unix_server", _rec_unix)
    monkeypatch.setattr(cli_server, "start_tcp_server", _rec_tcp)
    monkeypatch.setattr(cli_server, "start_ipc_server", _rec_ipc)
    monkeypatch.setattr(cli_server, "send_ack", _rec_ack)
    return calls


# --------------------------------------------------------------------------- #
# _serve: channel selection                                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("use_tcp", [False, True])
def test_serve_without_http_serves_ipc_only(monkeypatch, use_tcp):
    calls = _stub_channels(monkeypatch)
    asyncio.run(
        cli_server._serve(
            "/tmp/ack.sock",
            "/tmp/run-1.sock",
            "agent.pipe",
            8765,
            use_tcp,
            serve_http=False,
        )
    )
    assert calls == {"ipc": "agent.pipe"}


def test_serve_uses_the_explicit_ipc_pipe_name(monkeypatch):
    calls = _stub_channels(monkeypatch)
    asyncio.run(
        cli_server._serve(
            "/tmp/ack.sock", None, "my-agent-pipe", 8765, False, serve_http=False
        )
    )
    assert calls["ipc"] == "my-agent-pipe"


def test_serve_with_http_and_ipc_pipe_serves_both(monkeypatch):
    calls = _stub_channels(monkeypatch)
    asyncio.run(
        cli_server._serve("/tmp/ack.sock", "/tmp/run-1.sock", "agent.pipe", 8765, False)
    )
    assert calls == {
        "unix": ("/tmp/ack.sock", "/tmp/run-1.sock"),
        "ipc": "agent.pipe",
    }


def test_serve_without_ipc_pipe_serves_unix_http(monkeypatch):
    calls = _stub_channels(monkeypatch)
    asyncio.run(
        cli_server._serve("/tmp/ack.sock", "/tmp/run-1.sock", None, 8765, False)
    )
    assert calls == {"unix": ("/tmp/ack.sock", "/tmp/run-1.sock")}


def test_serve_without_ipc_pipe_serves_tcp_http(monkeypatch):
    calls = _stub_channels(monkeypatch)
    asyncio.run(cli_server._serve("/tmp/ack.sock", None, None, 9000, True))
    assert calls == {"tcp": ("127.0.0.1", 9000)}


def test_run_server_with_ipc_pipe_starts_neither_http_listener_nor_ack(monkeypatch):
    """Drives the real ``_run_server`` → ``_serve`` on the per-OS loop."""
    calls = _stub_channels(monkeypatch)
    cli_server._run_server(None, None, "agent.pipe", None, False)
    assert calls == {"ipc": "agent.pipe"}


def test_run_server_with_http_sockets_and_ipc_pipe_serves_both(monkeypatch):
    """The command line an older handler builds keeps its HTTP channel."""
    calls = _stub_channels(monkeypatch)
    cli_server._run_server(
        "/tmp/ack.sock", "/tmp/run-1.sock", "agent.pipe", None, False
    )
    assert calls["ipc"] == "agent.pipe"
    assert ("unix" in calls) is not cli_server.IS_WINDOWS
    assert ("tcp" in calls) is cli_server.IS_WINDOWS


# --------------------------------------------------------------------------- #
# _run_server: argument resolution + per-OS loop                              #
# --------------------------------------------------------------------------- #


def _capture_serve(monkeypatch) -> dict[str, Any]:
    """Replace ``_serve`` with an async recorder so ``_run_server`` runs to
    completion on its real per-OS loop (Proactor on Windows, ``asyncio.run`` on
    Linux) without actually serving anything."""
    seen: dict[str, Any] = {}

    async def _rec_serve(
        ack_socket_path, server_socket, ipc_pipe, port, use_tcp, serve_http=True
    ):
        seen.update(
            ack=ack_socket_path,
            server_socket=server_socket,
            ipc_pipe=ipc_pipe,
            port=port,
            use_tcp=use_tcp,
            serve_http=serve_http,
        )

    monkeypatch.setattr(cli_server, "_serve", _rec_serve)
    return seen


def test_run_server_defaults_ack_from_env(monkeypatch):
    seen = _capture_serve(monkeypatch)
    monkeypatch.setenv(cli_server.SOCKET_ENV_VAR, "/tmp/from-env.sock")
    cli_server._run_server(None, "/tmp/s.sock", None, None, False)
    assert seen["ack"] == "/tmp/from-env.sock"
    assert seen["server_socket"] == "/tmp/s.sock"
    assert seen["ipc_pipe"] is None
    assert seen["port"] == cli_server.DEFAULT_PORT
    assert seen["use_tcp"] is cli_server.IS_WINDOWS  # UDS on Linux, TCP on Windows


def test_run_server_passes_ipc_pipe_through(monkeypatch):
    seen = _capture_serve(monkeypatch)
    cli_server._run_server(None, None, "agent.pipe", None, False)
    assert seen["ipc_pipe"] == "agent.pipe"
    assert seen["serve_http"] is False


def test_run_server_without_ipc_pipe_serves_http(monkeypatch):
    seen = _capture_serve(monkeypatch)
    cli_server._run_server(None, None, None, None, False)
    assert seen["serve_http"] is True


@pytest.mark.parametrize(
    ("client_socket", "server_socket", "port", "tcp"),
    [
        ("/tmp/ack.sock", None, None, False),
        (None, "/tmp/run.sock", None, False),
        (None, None, 9000, False),
        (None, None, None, True),
    ],
)
def test_run_server_any_http_option_keeps_http_next_to_the_pipe(
    monkeypatch, client_socket, server_socket, port, tcp
):
    seen = _capture_serve(monkeypatch)
    cli_server._run_server(client_socket, server_socket, "agent.pipe", port, tcp)
    assert seen["ipc_pipe"] == "agent.pipe"
    assert seen["serve_http"] is True


def test_run_server_prefers_explicit_client_socket(monkeypatch):
    seen = _capture_serve(monkeypatch)
    monkeypatch.setenv(cli_server.SOCKET_ENV_VAR, "/tmp/from-env.sock")
    cli_server._run_server("/tmp/explicit.sock", "/tmp/s.sock", None, 1234, False)
    assert seen["ack"] == "/tmp/explicit.sock"  # explicit arg beats the env var
    assert seen["port"] == 1234


def test_run_server_falls_back_to_default_ack(monkeypatch):
    seen = _capture_serve(monkeypatch)
    monkeypatch.delenv(cli_server.SOCKET_ENV_VAR, raising=False)
    cli_server._run_server(None, "/tmp/s.sock", None, None, False)
    assert seen["ack"] == cli_server.DEFAULT_SOCKET_PATH


def test_run_server_tcp_flag_forces_tcp(monkeypatch):
    seen = _capture_serve(monkeypatch)
    cli_server._run_server("/tmp/a.sock", "/tmp/s.sock", None, None, True)
    assert seen["use_tcp"] is True


# --------------------------------------------------------------------------- #
# CLI validation + wiring                                                     #
# --------------------------------------------------------------------------- #


def _stub_cli(monkeypatch) -> dict[str, Any]:
    """Disable telemetry, record preload and the args the CLI hands _run_server."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(_telemetry, "is_telemetry_enabled", lambda: False)
    monkeypatch.setattr(
        cli_server, "preload_modules", lambda: seen.update(preloaded=True)
    )
    monkeypatch.setattr(
        cli_server,
        "_run_server",
        lambda client_socket, server_socket, ipc_pipe, port, tcp: seen.update(
            client_socket=client_socket,
            server_socket=server_socket,
            ipc_pipe=ipc_pipe,
            port=port,
            tcp=tcp,
        ),
    )
    return seen


def test_cli_passes_http_socket_args_through(monkeypatch):
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(
        cli_server.server,
        ["--client-socket", "/tmp/ack.sock", "--server-socket", "/tmp/run.sock"],
    )
    assert result.exit_code == 0, result.output
    assert seen["client_socket"] == "/tmp/ack.sock"
    assert seen["server_socket"] == "/tmp/run.sock"
    assert seen["ipc_pipe"] is None
    assert seen["tcp"] is False
    assert seen["preloaded"] is True


def test_cli_passes_tcp_args_through(monkeypatch):
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(cli_server.server, ["--tcp", "--port", "9000"])
    assert result.exit_code == 0, result.output
    assert seen["tcp"] is True
    assert seen["port"] == 9000
    assert seen["ipc_pipe"] is None


def test_cli_without_options_serves_http(monkeypatch):
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(cli_server.server, [])
    assert result.exit_code == 0, result.output
    assert seen["server_socket"] is None
    assert seen["ipc_pipe"] is None


def test_cli_ipc_pipe_alone_is_accepted(monkeypatch):
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(cli_server.server, ["--ipc-pipe", "agent.pipe"])
    assert result.exit_code == 0, result.output
    assert seen["ipc_pipe"] == "agent.pipe"
    assert seen["client_socket"] is None
    assert seen["server_socket"] is None
    assert seen["port"] is None
    assert seen["tcp"] is False
    assert seen["preloaded"] is True


def test_cli_passes_ipc_pipe_with_http_options_through(monkeypatch):
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(
        cli_server.server,
        [
            "--client-socket",
            "/tmp/ack.sock",
            "--server-socket",
            "/tmp/run.sock",
            "--ipc-pipe",
            "agent.pipe",
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen["client_socket"] == "/tmp/ack.sock"
    assert seen["server_socket"] == "/tmp/run.sock"
    assert seen["ipc_pipe"] == "agent.pipe"
    assert seen["preloaded"] is True


def test_cli_rejects_empty_ipc_pipe(monkeypatch):
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(cli_server.server, ["--ipc-pipe", ""])
    assert result.exit_code != 0
    assert "--ipc-pipe" in result.output
    assert seen == {}
