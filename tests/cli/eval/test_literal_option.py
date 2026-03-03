"""Tests for LiteralOption CLI option parsing (json.loads-based).

Regression tests for the fix that replaced ast.literal_eval with json.loads
to properly handle JSON values like null, true, and false.
"""

import click
from click.testing import CliRunner

from uipath._cli.cli_eval import LiteralOption


@click.command()
@click.option("--data", cls=LiteralOption, default="{}")
def dummy_command(data):
    """Dummy command for testing LiteralOption."""
    click.echo(repr(data))


class TestLiteralOption:
    """Test LiteralOption parses JSON correctly."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_parse_empty_dict(self):
        """Should parse empty JSON object."""
        result = self.runner.invoke(dummy_command, ["--data", "{}"])
        assert result.exit_code == 0
        assert "{}" in result.output

    def test_parse_empty_list(self):
        """Should parse empty JSON array."""
        result = self.runner.invoke(dummy_command, ["--data", "[]"])
        assert result.exit_code == 0
        assert "[]" in result.output

    def test_parse_dict_with_strings(self):
        """Should parse JSON object with string values."""
        result = self.runner.invoke(
            dummy_command, ["--data", '{"key": "value"}']
        )
        assert result.exit_code == 0
        assert "key" in result.output
        assert "value" in result.output

    def test_parse_dict_with_numbers(self):
        """Should parse JSON object with numeric values."""
        result = self.runner.invoke(
            dummy_command, ["--data", '{"a": 10, "b": 3.14}']
        )
        assert result.exit_code == 0
        assert "10" in result.output

    def test_parse_json_null(self):
        """Regression: should parse JSON null (ast.literal_eval fails on this)."""
        result = self.runner.invoke(
            dummy_command, ["--data", '{"field": null}']
        )
        assert result.exit_code == 0
        assert "None" in result.output

    def test_parse_json_true(self):
        """Regression: should parse JSON true (ast.literal_eval fails on this)."""
        result = self.runner.invoke(
            dummy_command, ["--data", '{"flag": true}']
        )
        assert result.exit_code == 0
        assert "True" in result.output

    def test_parse_json_false(self):
        """Regression: should parse JSON false (ast.literal_eval fails on this)."""
        result = self.runner.invoke(
            dummy_command, ["--data", '{"flag": false}']
        )
        assert result.exit_code == 0
        assert "False" in result.output

    def test_parse_json_with_mixed_null_true_false(self):
        """Regression: should parse JSON with null, true, and false together."""
        result = self.runner.invoke(
            dummy_command,
            ["--data", '{"a": null, "b": true, "c": false, "d": 42}'],
        )
        assert result.exit_code == 0
        assert "None" in result.output
        assert "True" in result.output
        assert "False" in result.output

    def test_parse_nested_input_overrides(self):
        """Should parse nested input overrides with file attachment structure."""
        json_str = '{"eval-1": {"filePath": {"ID": "550e8400-e29b-41d4-a716-446655440000", "FullName": "doc.pdf", "MimeType": "application/pdf"}}}'
        result = self.runner.invoke(dummy_command, ["--data", json_str])
        assert result.exit_code == 0
        assert "550e8400-e29b-41d4-a716-446655440000" in result.output

    def test_parse_input_overrides_with_null_values(self):
        """Regression: should parse input overrides containing null values."""
        json_str = '{"eval-1": {"filePath": {"ID": "550e8400-e29b-41d4-a716-446655440000", "Metadata": null}}}'
        result = self.runner.invoke(dummy_command, ["--data", json_str])
        assert result.exit_code == 0
        assert "None" in result.output
        assert "550e8400-e29b-41d4-a716-446655440000" in result.output

    def test_parse_list_of_strings(self):
        """Should parse JSON array of strings."""
        result = self.runner.invoke(
            dummy_command, ["--data", '["eval-1", "eval-2", "eval-3"]']
        )
        assert result.exit_code == 0
        assert "eval-1" in result.output

    def test_invalid_json_raises_bad_parameter(self):
        """Should raise BadParameter for invalid JSON."""
        result = self.runner.invoke(
            dummy_command, ["--data", "{invalid json}"]
        )
        assert result.exit_code != 0

    def test_default_value(self):
        """Should use default empty dict when no value provided."""
        result = self.runner.invoke(dummy_command, [])
        assert result.exit_code == 0
        assert "{}" in result.output
