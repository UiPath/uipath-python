"""Integration tests for --format json across CLI commands."""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli._utils._console import ConsoleLogger


@pytest.fixture(autouse=True)
def reset_cli_logger():
    """Reset ConsoleLogger singleton between tests."""
    ConsoleLogger._instance = None
    yield
    ConsoleLogger._instance = None


class TestJsonOutputIntegration:
    def test_help_json(self):
        """Top-level --help with --format json returns valid JSON."""
        runner = CliRunner()
        # _get_format_from_argv reads sys.argv, so we must patch it
        with patch("sys.argv", ["uipath", "--format", "json", "--help"]):
            result = runner.invoke(cli, ["--format", "json", "--help"])
        output = json.loads(result.output)
        assert "name" in output
        assert "commands" in output

    def test_version_still_works_with_format_json(self):
        """--version still works with --format json."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "--version"])
        assert result.exit_code == 0

    def test_assets_list_no_auth_json_error(self):
        """assets list without auth returns error exit code."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "assets", "list"])
        assert result.exit_code != 0

    def test_buckets_list_no_auth_json_error(self):
        """buckets list without auth returns error exit code."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "buckets", "list"])
        assert result.exit_code != 0

    def test_default_format_is_text(self):
        """Default --format is text (no JSON)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        # Default help should NOT be JSON
        assert result.exit_code == 0
        assert "UiPath CLI" in result.output

    def test_subcommand_help_with_format_json(self):
        """Subcommand help with --format json doesn't crash."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "assets", "--help"])
        assert result.exit_code == 0
        assert "assets" in result.output.lower()
