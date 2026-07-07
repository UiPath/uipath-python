import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

from uipath._cli import cli, cli_dev
from uipath._cli.middlewares import MiddlewareResult
from uipath.platform.common import UiPathExecutionContext


def test_create_dev_context_and_factory_uses_dev_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The helper builds a 'dev' context (source 'playground') and its factory."""
    sentinel_factory = MagicMock(name="factory")
    captured: dict[str, object] = {}

    def fake_get(context: object) -> object:
        captured["command"] = context.command  # type: ignore[attr-defined]
        return sentinel_factory

    monkeypatch.setattr(
        "uipath._cli.cli_dev.UiPathRuntimeFactoryRegistry.get", fake_get
    )

    context, factory = cli_dev._create_dev_context_and_factory(None)  # type: ignore[arg-type]

    assert factory is sentinel_factory
    assert captured["command"] == "dev"
    assert context.execution_source == "playground"


def test_dev_terminal_sets_execution_source_during_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running `dev terminal` scopes the execution source to 'playground'."""
    seen: dict[str, object] = {}

    async def fake_run_async() -> None:
        seen["source"] = UiPathExecutionContext().execution_source

    fake_console = MagicMock()
    fake_console.run_async = fake_run_async

    fake_module = types.ModuleType("uipath.dev")
    fake_module.UiPathDeveloperConsole = MagicMock(return_value=fake_console)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uipath.dev", fake_module)

    mock_factory = MagicMock()
    mock_factory.dispose = AsyncMock()

    monkeypatch.setattr(cli_dev, "_check_dev_dependency", lambda interface: None)
    monkeypatch.setattr(cli_dev, "setup_debugging", lambda debug, port: True)
    monkeypatch.setattr(
        "uipath._cli.cli_dev.Middlewares.next",
        lambda *a, **k: MiddlewareResult(should_continue=True),
    )
    monkeypatch.setattr(
        "uipath._cli.cli_dev.UiPathRuntimeFactoryRegistry.get",
        lambda context: mock_factory,
    )

    result = CliRunner().invoke(cli, ["dev", "terminal"])

    assert result.exit_code == 0, result.output
    assert seen["source"] == "playground"
    # token released once the run completes
    assert UiPathExecutionContext().execution_source is None
