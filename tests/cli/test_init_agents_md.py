"""Tests for AGENTS.md generation in the init command."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.cli_init import (  # type: ignore[attr-defined]
    generate_agent_md_file,
    generate_agent_md_files,
)


class TestGenerateAgentMdFile:
    """Test the generate_agent_md_file helper function."""

    def test_generate_agent_md_file_creates_file(self) -> None:
        """Test that a single md file is created successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                mock_source = (
                    Path(__file__).parent.parent.parent
                    / "src"
                    / "uipath"
                    / "_resources"
                    / "AGENTS.md"
                )

                with (
                    patch(
                        "uipath._cli.cli_init.importlib.resources.files"
                    ) as mock_files,
                    patch(
                        "uipath._cli.cli_init.importlib.resources.as_file"
                    ) as mock_as_file,
                ):
                    mock_path = MagicMock()
                    mock_files.return_value.joinpath.return_value = mock_path
                    mock_as_file.return_value.__enter__.return_value = mock_source
                    mock_as_file.return_value.__exit__.return_value = None

                    generate_agent_md_file(temp_dir, "AGENTS.md", False)

                    assert (Path(temp_dir) / "AGENTS.md").exists()
            finally:
                os.chdir(original_cwd)

    def test_generate_agents_md_overwrites_existing_file(self) -> None:
        """Test that existing AGENTS.md is overwritten."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_path = Path(temp_dir) / "AGENTS.md"
            original_content = "Original content"
            agents_path.write_text(original_content)

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
                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = mock_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_file(temp_dir, "AGENTS.md", False)

                assert agents_path.read_text() != original_content
                assert agents_path.exists()

    def test_generate_agents_md_handles_errors_gracefully(self) -> None:
        """Test that errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch("uipath._cli.cli_init.console") as mock_console,
            ):
                mock_files.side_effect = RuntimeError("Test error")

                generate_agent_md_file(temp_dir, "AGENTS.md", False)

                mock_console.warning.assert_called_once()
                assert "Could not create AGENTS.md: Test error" in str(
                    mock_console.warning.call_args
                )


class TestGenerateAgentMdFiles:
    """Test the generate_agent_md_files function that creates multiple files."""

    def test_generate_agent_md_files_creates_all_files(self) -> None:
        """Test that all root and agent files are created in the correct locations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
                patch("uipath._cli.cli_init.console"),
                patch("uipath._cli._runtime._runtime.console"),
            ):
                temp_source = Path(temp_dir) / "temp_source.md"
                temp_source.write_text("Test content")

                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = temp_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_files(temp_dir, False)

                agent_dir = Path(temp_dir) / ".agent"
                assert agent_dir.exists()
                assert agent_dir.is_dir()

                assert (Path(temp_dir) / "AGENTS.md").exists()
                assert (Path(temp_dir) / "CLAUDE.md").exists()

                assert (agent_dir / "CLI_REFERENCE.md").exists()
                assert (agent_dir / "REQUIRED_STRUCTURE.md").exists()
                assert (agent_dir / "SDK_REFERENCE.md").exists()

    def test_generate_agent_md_files_overwrites_existing_files(self) -> None:
        """Test that existing files are overwritten."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agent_dir = Path(temp_dir) / ".agent"
            agent_dir.mkdir()

            agents_path = Path(temp_dir) / "AGENTS.md"
            agents_content = "Original AGENTS content"
            agents_path.write_text(agents_content)

            cli_ref_path = agent_dir / "CLI_REFERENCE.md"
            cli_ref_content = "Original CLI_REFERENCE content"
            cli_ref_path.write_text(cli_ref_content)

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
                patch("uipath._cli.cli_init.console"),
            ):
                temp_source = Path(temp_dir) / "temp_source.md"
                temp_source.write_text("Test content")

                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = temp_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_files(temp_dir, False)

                assert agents_path.read_text() != agents_content
                assert agents_path.read_text() == "Test content"
                assert cli_ref_path.read_text() != cli_ref_content
                assert cli_ref_path.read_text() == "Test content"


class TestInitWithAgentsMd:
    """Test the init command with default AGENTS.md creation."""

    def test_init_creates_agent_files_by_default(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that agent files are created by default during init."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a simple Python file
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            temp_source = Path(temp_dir) / "temp_source.md"
            temp_source.write_text("Test content")

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
            ):
                # Setup mocks
                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = temp_source
                mock_as_file.return_value.__exit__.return_value = None

                result = runner.invoke(cli, ["init"])

                assert result.exit_code == 0
                assert "AGENTS.md" in result.output
                assert "file." in result.output

                assert os.path.exists("AGENTS.md")
                assert os.path.exists("CLAUDE.md")

                assert os.path.exists(".agent/CLI_REFERENCE.md")
                assert os.path.exists(".agent/REQUIRED_STRUCTURE.md")
                assert os.path.exists(".agent/SDK_REFERENCE.md")

    def test_init_overwrites_existing_agents_md(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that existing AGENTS.md is overwritten."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a simple Python file
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            # Create existing AGENTS.md
            original_content = "Original AGENTS.md content"
            with open("AGENTS.md", "w") as f:
                f.write(original_content)

            temp_source = Path(temp_dir) / "temp_source.md"
            temp_source.write_text("Test content")

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
            ):
                # Setup mocks
                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = temp_source
                mock_as_file.return_value.__exit__.return_value = None

                # Run init (AGENTS.md creation is now default)
                result = runner.invoke(cli, ["init"])

                assert result.exit_code == 0

                # Verify content was changed
                with open("AGENTS.md", "r") as f:
                    content = f.read()
                    assert content != original_content
                    assert content == "Test content"
