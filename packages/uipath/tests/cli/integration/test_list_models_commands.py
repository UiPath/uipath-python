"""Integration tests for the `uipath list-models` CLI command.

The command renders a rich table grouped by vendor (one column per vendor)
for human terminal use, and falls through to the shared `format_output`
pipeline for `--format json|csv` and `--output <file>`.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath.platform.agenthub import LlmModel


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Provide a mocked UiPath client with an async agenthub service."""
    with patch("uipath.platform._uipath.UiPath") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance

        client_instance.agenthub = MagicMock()
        client_instance.agenthub.get_available_llm_models_async = AsyncMock()

        yield client_instance


def _make_models() -> list[LlmModel]:
    """Build a small list of LlmModel instances spanning multiple vendors."""
    return [
        LlmModel(model_name="gpt-4o-mini", vendor="OpenAi"),
        LlmModel(model_name="gpt-4.1", vendor="OpenAi"),
        LlmModel(model_name="claude-sonnet-4-5", vendor="Anthropic"),
        LlmModel(model_name="gemini-2.5-flash", vendor="VertexAi"),
    ]


class TestRichTable:
    def test_renders_each_model_and_vendor(self, runner, mock_client, mock_env_vars):
        """All models and vendor headers appear in the rendered table."""
        mock_client.agenthub.get_available_llm_models_async.return_value = (
            _make_models()
        )

        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code == 0
        for model in _make_models():
            assert model.model_name in result.output
            assert (model.vendor or "") in result.output
        mock_client.agenthub.get_available_llm_models_async.assert_awaited_once()

    def test_table_title(self, runner, mock_client, mock_env_vars):
        """The rich table renders its title for orientation."""
        mock_client.agenthub.get_available_llm_models_async.return_value = (
            _make_models()
        )

        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code == 0
        assert "Available LLM Models" in result.output

    def test_missing_vendor_grouped_under_unknown(
        self, runner, mock_client, mock_env_vars
    ):
        """A model with no vendor lands in an 'Unknown' column."""
        mock_client.agenthub.get_available_llm_models_async.return_value = [
            LlmModel(model_name="custom-model", vendor=None),
        ]

        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code == 0
        assert "custom-model" in result.output
        assert "Unknown" in result.output

    def test_empty(self, runner, mock_client, mock_env_vars):
        """An empty model list renders the title without rows or errors."""
        mock_client.agenthub.get_available_llm_models_async.return_value = []

        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code == 0
        assert "Available LLM Models" in result.output


class TestMachineReadableFormats:
    def test_json_format(self, runner, mock_client, mock_env_vars):
        """--format json bypasses the rich table and emits parseable JSON."""
        mock_client.agenthub.get_available_llm_models_async.return_value = (
            _make_models()
        )

        result = runner.invoke(cli, ["list-models", "--format", "json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert isinstance(payload, list)
        assert {m["model_name"] for m in payload} == {
            "gpt-4o-mini",
            "gpt-4.1",
            "claude-sonnet-4-5",
            "gemini-2.5-flash",
        }

    def test_csv_format(self, runner, mock_client, mock_env_vars):
        """--format csv emits a header row and one row per model."""
        mock_client.agenthub.get_available_llm_models_async.return_value = (
            _make_models()
        )

        result = runner.invoke(cli, ["list-models", "--format", "csv"])

        assert result.exit_code == 0
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert "model_name" in lines[0]
        assert "vendor" in lines[0]
        assert any("gpt-4o-mini" in line for line in lines[1:])

    def test_global_json_flag(self, runner, mock_client, mock_env_vars):
        """The cli-group --format json is honored too."""
        mock_client.agenthub.get_available_llm_models_async.return_value = (
            _make_models()
        )

        result = runner.invoke(cli, ["--format", "json", "list-models"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload) == 4

    def test_output_writes_through_plain_formatter(
        self, runner, mock_client, mock_env_vars, tmp_path
    ):
        """--output writes through format_output (not the rich path)."""
        mock_client.agenthub.get_available_llm_models_async.return_value = (
            _make_models()
        )
        out_file = tmp_path / "models.json"

        result = runner.invoke(
            cli,
            ["list-models", "--format", "json", "--output", str(out_file)],
        )

        assert result.exit_code == 0
        assert out_file.exists()
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        assert {m["model_name"] for m in payload} == {
            "gpt-4o-mini",
            "gpt-4.1",
            "claude-sonnet-4-5",
            "gemini-2.5-flash",
        }

    def test_output_file_alias(self, runner, mock_client, mock_env_vars, tmp_path):
        """`--output-file` works as an alias for `--output` (matches `run`)."""
        mock_client.agenthub.get_available_llm_models_async.return_value = (
            _make_models()
        )
        out_file = tmp_path / "models.json"

        result = runner.invoke(
            cli,
            ["list-models", "--format", "json", "--output-file", str(out_file)],
        )

        assert result.exit_code == 0
        assert out_file.exists()
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        assert len(payload) == 4


class TestErrorPaths:
    def test_service_error(self, runner, mock_client, mock_env_vars):
        """Exceptions from the service are surfaced as click errors."""
        mock_client.agenthub.get_available_llm_models_async.side_effect = RuntimeError(
            "boom"
        )

        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code != 0
        assert "boom" in result.output

    def test_missing_url(self, runner, monkeypatch):
        """Missing UIPATH_URL surfaces an auth-configuration error."""
        monkeypatch.delenv("UIPATH_URL", raising=False)
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "mock_token")

        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code != 0
        assert "UIPATH_URL not configured" in result.output

    def test_missing_token(self, runner, monkeypatch):
        """Missing UIPATH_ACCESS_TOKEN surfaces an auth-configuration error."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.delenv("UIPATH_ACCESS_TOKEN", raising=False)

        result = runner.invoke(cli, ["list-models"])

        assert result.exit_code != 0
        assert "Authentication required" in result.output


class TestRegistration:
    def test_help_text(self, runner):
        """--help surfaces the command description and options."""
        result = runner.invoke(cli, ["list-models", "--help"])

        assert result.exit_code == 0
        assert "List available LLM models" in result.output
        assert "--format" in result.output
        assert "--output" in result.output
        assert "--output-file" in result.output

    def test_registered_in_cli(self, runner):
        """The command is wired into the top-level CLI group."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "list-models" in result.output
