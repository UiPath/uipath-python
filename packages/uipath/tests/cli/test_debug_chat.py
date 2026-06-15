# type: ignore
"""Tests for chat runtime wiring in the debug command."""

import json
from unittest.mock import AsyncMock, Mock, patch

from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult
from uipath.runtime import UiPathRuntimeResult, UiPathRuntimeStatus


class TestDebugConversationalExchangeEnd:
    """Debug runs pass the endExchange fps property to UiPathChatRuntime."""

    def _invoke_debug(self, runner: CliRunner, chat_runtime_cls):
        mock_runtime = Mock()
        mock_runtime.dispose = AsyncMock()
        mock_runtime.get_schema = AsyncMock(return_value=Mock(metadata=None))

        mock_factory = Mock()
        mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)
        mock_factory.get_settings = AsyncMock(return_value=Mock(trace_settings=None))
        mock_factory.dispose = AsyncMock()

        mock_debug_runtime = Mock()
        mock_debug_runtime.dispose = AsyncMock()

        mock_mock_runtime = Mock()
        mock_mock_runtime.execute = AsyncMock(
            return_value=UiPathRuntimeResult(status=UiPathRuntimeStatus.SUCCESSFUL)
        )
        mock_mock_runtime.dispose = AsyncMock()

        with (
            patch(
                "uipath._cli.cli_debug.Middlewares.next",
                return_value=MiddlewareResult(
                    should_continue=True,
                    error_message=None,
                    should_include_stacktrace=False,
                ),
            ),
            patch(
                "uipath._cli.cli_debug.UiPathRuntimeFactoryRegistry.get",
                return_value=mock_factory,
            ),
            patch("uipath._cli.cli_debug.get_debug_bridge"),
            patch("uipath._cli.cli_debug.get_chat_bridge"),
            patch(
                "uipath._cli.cli_debug.UiPathDebugRuntime",
                return_value=mock_debug_runtime,
            ),
            patch(
                "uipath._cli.cli_debug.UiPathMockRuntime",
                return_value=mock_mock_runtime,
            ),
        ):
            return runner.invoke(cli, ["debug", "main", "{}"])

    def test_end_exchange_false_passed_to_chat_runtime(
        self, runner: CliRunner, temp_dir: str, monkeypatch
    ):
        """endExchange=false in fpsProperties reaches the UiPathChatRuntime constructor."""
        monkeypatch.setenv("UIPATH_TRACING_ENABLED", "false")
        monkeypatch.delenv("UIPATH_CONFIG_PATH", raising=False)

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump(
                    {
                        "fpsProperties": {
                            "conversationalService.conversationId": "conv-1",
                            "conversationalService.exchangeId": "ex-1",
                            "conversationalService.endExchange": False,
                        }
                    },
                    f,
                )

            mock_chat_runtime = Mock()
            mock_chat_runtime.dispose = AsyncMock()
            with patch(
                "uipath._cli.cli_debug.UiPathChatRuntime",
                return_value=mock_chat_runtime,
            ) as chat_runtime_cls:
                result = self._invoke_debug(runner, chat_runtime_cls)

            assert result.exit_code == 0, (
                f"output: {result.output!r}, exception: {result.exception}"
            )
            assert chat_runtime_cls.called
            assert chat_runtime_cls.call_args.kwargs.get("end_exchange") is False
