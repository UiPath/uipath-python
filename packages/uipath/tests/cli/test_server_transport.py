"""`uipath server` serves BOTH transports concurrently — never either/or.

The HTTP channel (aiohttp over a Unix socket, or TCP on Windows / ``--tcp``) is
ALWAYS started. The uipath-ipc named-pipe channel is started alongside it when a
``--server-socket`` is given, with the pipe name the socket's basename (directory
stripped, extension kept), matching the .NET side. The HTTP channel is never torn
down.

These tests stub the three channel runners (so ``_serve``'s ``asyncio.gather``
returns at once instead of serving forever) and assert which channels ``_serve``
composes, how ``_run_server`` resolves its arguments, and that the CLI wires them
through.
"""

import asyncio

from click.testing import CliRunner

import uipath._cli._telemetry as _telemetry
from uipath._cli import cli_server


def _stub_channels(monkeypatch) -> dict:
    """Stub the three channel runners + state init; record what ``_serve`` starts.

    Each runner is replaced with an async recorder that returns immediately, so
    ``_serve``'s ``asyncio.gather`` completes instead of blocking in serve-forever.
    ``_state.init`` is stubbed too, so no event-loop-bound lock leaks between the
    per-test loops ``asyncio.run`` creates.
    """
    calls: dict = {}

    async def _rec_unix(ack_socket_path, server_socket_path=None):
        calls["unix"] = (ack_socket_path, server_socket_path)

    async def _rec_tcp(host, port):
        calls["tcp"] = (host, port)

    async def _rec_ipc(pipe_name):
        calls["ipc"] = pipe_name

    monkeypatch.setattr(cli_server._state, "init", lambda: None)
    monkeypatch.setattr(cli_server, "start_unix_server", _rec_unix)
    monkeypatch.setattr(cli_server, "start_tcp_server", _rec_tcp)
    monkeypatch.setattr(cli_server, "start_ipc_server", _rec_ipc)
    return calls


# --------------------------------------------------------------------------- #
# _serve: channel composition                                                 #
# --------------------------------------------------------------------------- #


def test_serve_runs_http_and_ipc_together(monkeypatch):
    calls = _stub_channels(monkeypatch)
    asyncio.run(cli_server._serve("/tmp/ack.sock", "/tmp/run-1.sock", 8765, False))
    assert calls["unix"] == ("/tmp/ack.sock", "/tmp/run-1.sock")
    assert calls["ipc"] == "run-1.sock"  # pipe = socket basename (directory stripped)
    assert "tcp" not in calls


def test_serve_derives_pipe_name_from_socket_basename(monkeypatch):
    calls = _stub_channels(monkeypatch)
    asyncio.run(
        cli_server._serve("/tmp/ack.sock", "/var/tmp/uipath-server-42.sock", 8765, False)
    )
    assert calls["ipc"] == "uipath-server-42.sock"  # basename (directory stripped, extension kept)


def test_serve_rides_ipc_alongside_tcp(monkeypatch):
    calls = _stub_channels(monkeypatch)
    asyncio.run(cli_server._serve("/tmp/ack.sock", "/tmp/run-1.sock", 9000, True))
    assert calls["tcp"] == ("127.0.0.1", 9000)
    assert "unix" not in calls
    assert calls["ipc"] == "run-1.sock"  # IPC is served next to TCP too, not only UDS


def test_serve_skips_ipc_without_server_socket(monkeypatch):
    """No ``--server-socket`` ⇒ HTTP only (no pipe name to derive)."""
    calls = _stub_channels(monkeypatch)
    asyncio.run(cli_server._serve("/tmp/ack.sock", None, 8765, False))
    assert calls["unix"] == ("/tmp/ack.sock", None)
    assert "ipc" not in calls


# --------------------------------------------------------------------------- #
# _run_server: argument resolution + per-OS loop                              #
# --------------------------------------------------------------------------- #


def _capture_serve(monkeypatch) -> dict:
    """Replace ``_serve`` with an async recorder so ``_run_server`` runs to
    completion on its real per-OS loop (Proactor on Windows, ``asyncio.run`` on
    Linux) without actually serving anything."""
    seen: dict = {}

    async def _rec_serve(ack_socket_path, server_socket, port, use_tcp):
        seen.update(
            ack=ack_socket_path,
            server_socket=server_socket,
            port=port,
            use_tcp=use_tcp,
        )

    monkeypatch.setattr(cli_server, "_serve", _rec_serve)
    return seen


def test_run_server_defaults_ack_from_env(monkeypatch):
    seen = _capture_serve(monkeypatch)
    monkeypatch.setenv(cli_server.SOCKET_ENV_VAR, "/tmp/from-env.sock")
    cli_server._run_server(None, "/tmp/s.sock", None, False)
    assert seen["ack"] == "/tmp/from-env.sock"
    assert seen["server_socket"] == "/tmp/s.sock"
    assert seen["port"] == cli_server.DEFAULT_PORT
    assert seen["use_tcp"] is cli_server.IS_WINDOWS  # UDS on Linux, TCP on Windows


def test_run_server_prefers_explicit_client_socket(monkeypatch):
    seen = _capture_serve(monkeypatch)
    monkeypatch.setenv(cli_server.SOCKET_ENV_VAR, "/tmp/from-env.sock")
    cli_server._run_server("/tmp/explicit.sock", "/tmp/s.sock", 1234, False)
    assert seen["ack"] == "/tmp/explicit.sock"  # explicit arg beats the env var
    assert seen["port"] == 1234


def test_run_server_falls_back_to_default_ack(monkeypatch):
    seen = _capture_serve(monkeypatch)
    monkeypatch.delenv(cli_server.SOCKET_ENV_VAR, raising=False)
    cli_server._run_server(None, "/tmp/s.sock", None, False)
    assert seen["ack"] == cli_server.DEFAULT_SOCKET_PATH


def test_run_server_tcp_flag_forces_tcp(monkeypatch):
    seen = _capture_serve(monkeypatch)
    cli_server._run_server("/tmp/a.sock", "/tmp/s.sock", None, True)
    assert seen["use_tcp"] is True


# --------------------------------------------------------------------------- #
# CLI wiring (backward-compatible single --server-socket)                     #
# --------------------------------------------------------------------------- #


def _stub_cli(monkeypatch) -> dict:
    """Disable telemetry + preload and record the args the CLI hands _run_server."""
    seen: dict = {}
    monkeypatch.setattr(_telemetry, "is_telemetry_enabled", lambda: False)
    monkeypatch.setattr(cli_server, "preload_modules", lambda: None)
    monkeypatch.setattr(
        cli_server,
        "_run_server",
        lambda client_socket, server_socket, port, tcp: seen.update(
            client_socket=client_socket,
            server_socket=server_socket,
            port=port,
            tcp=tcp,
        ),
    )
    return seen


def test_cli_passes_socket_args_through(monkeypatch):
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(
        cli_server.server,
        ["--client-socket", "/tmp/ack.sock", "--server-socket", "/tmp/run.sock"],
    )
    assert result.exit_code == 0, result.output
    assert seen["client_socket"] == "/tmp/ack.sock"
    assert seen["server_socket"] == "/tmp/run.sock"
    assert seen["tcp"] is False


def test_cli_server_socket_is_optional(monkeypatch):
    """No ``--server-socket`` is no longer an error: HTTP auto-generates one and
    the IPC channel is simply skipped."""
    seen = _stub_cli(monkeypatch)
    result = CliRunner().invoke(cli_server.server, [])
    assert result.exit_code == 0, result.output
    assert seen["server_socket"] is None
