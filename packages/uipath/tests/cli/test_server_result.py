"""The outcome a job reports back over both server channels.

``_run_command_isolated`` is the single job core behind the HTTP and uipath-ipc
channels, so the exit code it produces is what BOTH wires report. Click's
``standalone_mode=False`` returns ``ctx.exit(N)``'s code instead of raising
``SystemExit`` — these tests pin that behaviour against real click commands
rather than a stub, because it is the whole reason the exit code can be wrong.
"""

from typing import Any, cast

import click
import pytest
from aiohttp import web

from uipath._cli import _server_core, cli_server
from uipath._cli._server_core import _run_command_isolated, _ServerState
from uipath._cli._utils._console import ConsoleLogger


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    """Give each test a state object whose lock binds to that test's event loop."""
    monkeypatch.setattr(_server_core, "_state", _ServerState())


@click.command()
def _returns_object() -> dict[str, Any]:
    return {"ok": True}


@click.command()
def _returns_none() -> None:
    return None


@click.command()
def _exits_one() -> None:
    click.get_current_context().exit(1)


@click.command()
def _exits_zero() -> None:
    click.get_current_context().exit(0)


@click.command()
def _console_errors() -> None:
    ConsoleLogger().error("boom")


@click.command()
def _raises() -> None:
    raise RuntimeError("kaboom")


async def _run(cmd: Any) -> dict[str, Any]:
    _server_core._state.init()
    return await _run_command_isolated(cmd, [], {}, None)


# --------------------------------------------------------------------------- #
# exit-code normalisation                                                     #
# --------------------------------------------------------------------------- #


async def test_console_error_reports_a_failing_exit_code():
    """The regression that mattered: ConsoleLogger.error ends in ctx.exit(1), which
    click RETURNS under standalone_mode=False — it must not read as success."""
    result = await _run(_console_errors)

    assert result["ExitCode"] == 1
    assert result["Error"] == "Exit code: 1"
    assert result["Unexpected"] is False


async def test_ctx_exit_nonzero_becomes_the_exit_code():
    result = await _run(_exits_one)

    assert result["ExitCode"] == 1
    assert result["Result"] is None


async def test_ctx_exit_zero_is_success():
    result = await _run(_exits_zero)

    assert result["ExitCode"] == 0
    assert result["Error"] is None


async def test_object_return_is_a_result_not_an_exit_code():
    result = await _run(_returns_object)

    assert result["ExitCode"] == 0
    assert result["Error"] is None
    assert result["Result"] == {"ok": True}


async def test_none_return_is_success():
    result = await _run(_returns_none)

    assert result["ExitCode"] == 0
    assert result["Result"] is None


async def test_unhandled_exception_is_flagged_unexpected():
    result = await _run(_raises)

    assert result["ExitCode"] == 1
    assert result["Unexpected"] is True
    assert "kaboom" in result["Error"]


# --------------------------------------------------------------------------- #
# HTTP response envelope                                                      #
# --------------------------------------------------------------------------- #


class _FakeRequest:
    """Minimal stand-in for web.Request: handle_start only uses match_info + json()."""

    def __init__(self, job_key: str, payload: dict[str, Any]) -> None:
        self.match_info = {"job_key": job_key}
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload


async def _post_start(monkeypatch, command_result: dict[str, Any]) -> web.Response:
    async def _fake_isolated(cmd, args, env_vars, working_dir):
        return command_result

    monkeypatch.setattr(cli_server, "_run_command_isolated", _fake_isolated)
    request = cast(web.Request, _FakeRequest("job-1", {"command": "run"}))
    return await cli_server.handle_start(request)


async def test_success_body_carries_exit_code(monkeypatch):
    response = await _post_start(
        monkeypatch,
        {"ExitCode": 0, "Error": None, "Result": {"out": 1}, "Unexpected": False},
    )

    assert response.status == 200
    assert response.text is not None
    body = response.text
    assert '"success": true' in body
    assert '"exitCode": 0' in body


async def test_failure_body_is_200_but_says_so_and_carries_exit_code(monkeypatch):
    """A failed job answers 200 with the outcome in the body — so the body must be
    unambiguous. A handler reading only exitCode has to see a non-zero value."""
    response = await _post_start(
        monkeypatch,
        {"ExitCode": 1, "Error": "Exit code: 1", "Result": None, "Unexpected": False},
    )

    assert response.status == 200
    body = response.text or ""
    assert '"success": false' in body
    assert '"exitCode": 1' in body
    assert "Exit code: 1" in body


async def test_unexpected_failure_is_500(monkeypatch):
    response = await _post_start(
        monkeypatch,
        {"ExitCode": 1, "Error": "kaboom", "Result": None, "Unexpected": True},
    )

    assert response.status == 500


async def test_client_error_is_400(monkeypatch):
    response = await _post_start(
        monkeypatch,
        {
            "ExitCode": 1,
            "Error": "Cannot change to working directory",
            "Result": None,
            "Unexpected": False,
            "ClientError": True,
        },
    )

    assert response.status == 400
