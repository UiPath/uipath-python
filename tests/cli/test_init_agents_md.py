"""Tests for AGENTS.md generation in the init command."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.cli_init import (  # type: ignore[attr-defined]
    generate_agent_specific_file_md,
)


class TestGenerateAgentsMd:
    """Test the generate_agent_specific_file_md helper function."""

    def test_generate_agent_specific_file_md_creates_file(self) -> None:
        """Test that AGENTS.md is created successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock importlib.resources to return our test file
            mock_source = (
                Path(__file__).parent.parent.parent
                / "src"
                / "uipath"
                / "_resources"
                / "AGENTS.md"
            )

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
                patch("uipath._cli.cli_init.console") as mock_console,
            ):
                # Setup mocks
                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = mock_source
                mock_as_file.return_value.__exit__.return_value = None

                # Run function
                generate_agent_specific_file_md(temp_dir, "AGENTS.md")

                # Verify console success message
                mock_console.success.assert_called_once_with(
                    "Created '.agent/AGENTS.md' file."
                )

    def test_generate_agents_md_skips_existing_file(self) -> None:
        """Test that existing AGENTS.md is not overwritten."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create existing file
            agents_path = Path(temp_dir) / "AGENTS.md"
            original_content = "Original content"
            agents_path.write_text(original_content)

            # Run function
            generate_agent_specific_file_md(temp_dir, "AGENTS.md")

            # Verify file wasn't changed
            assert agents_path.read_text() == original_content

    def test_generate_agents_md_handles_errors_gracefully(self) -> None:
        """Test that errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch("uipath._cli.cli_init.console") as mock_console,
            ):
                # Make it raise an exception
                mock_files.side_effect = RuntimeError("Test error")

                # Run function - should not raise
                generate_agent_specific_file_md(temp_dir, "AGENTS.md")

                # Verify warning was logged
                mock_console.warning.assert_called_once()
                assert "Could not create AGENTS.md: Test error" in str(
                    mock_console.warning.call_args
                )


class TestInitWithAgentsMd:
    """Test the init command with default AGENTS.md creation."""

    def test_init_creates_agents_md_by_default(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that AGENTS.md is created by default."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a simple Python file
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            # Mock the AGENTS.md source file
            mock_source = (
                Path(__file__).parent.parent.parent
                / "src"
                / "uipath"
                / "_resources"
                / "AGENTS.md"
            )

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
            ):
                # Setup mocks
                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path

                # Check if the actual AGENTS.md exists, if so use it
                if mock_source.exists():
                    mock_as_file.return_value.__enter__.return_value = mock_source
                else:
                    # Create a temp file to copy
                    temp_agents = Path(temp_dir) / "temp_agents.md"
                    temp_agents.write_text("Test AGENTS.md content")
                    mock_as_file.return_value.__enter__.return_value = temp_agents

                mock_as_file.return_value.__exit__.return_value = None

                # Run init (AGENTS.md should be created by default)
                result = runner.invoke(cli, ["init"])

                assert result.exit_code == 0
                assert "Created '.agent/AGENTS.md' file." in result.output
                assert os.path.exists(".agent/AGENTS.md")

    def test_init_does_not_overwrite_existing_agents_md(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that existing AGENTS.md is not overwritten."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a simple Python file
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            # Create existing AGENTS.md
            original_content = "Original AGENTS.md content"
            with open("AGENTS.md", "w") as f:
                f.write(original_content)

            # Run init (AGENTS.md creation is now default)
            result = runner.invoke(cli, ["init"])

            assert result.exit_code == 0

            # Verify content wasn't changed
            with open("AGENTS.md", "r") as f:
                assert f.read() == original_content
