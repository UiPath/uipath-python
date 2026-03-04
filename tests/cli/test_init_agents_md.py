"""Tests for AGENTS.md and CLAUDE.md generation in the init command."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.cli_init import (
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

    def test_generate_claude_md_overwrites_existing_file(self) -> None:
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

    def test_generate_claude_md_handles_errors_gracefully(self) -> None:
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
    """Test the generate_agent_md_files function that creates AGENTS.md and CLAUDE.md."""

    def test_generate_agent_md_files_creates_agents_and_claude_md(self) -> None:
        """Test that AGENTS.md and CLAUDE.md are created (without .agent/ or .claude/commands/)."""
        with tempfile.TemporaryDirectory() as temp_dir:
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

                assert (Path(temp_dir) / "AGENTS.md").exists()
                assert (Path(temp_dir) / "CLAUDE.md").exists()

                # Should NOT create .agent directory or .claude/commands/
                assert not (Path(temp_dir) / ".agent").exists()
                assert not (Path(temp_dir) / ".claude" / "commands").exists()

    def test_generate_agent_md_files_overwrites_existing_agents_md(self) -> None:
        """Test that existing AGENTS.md is overwritten."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_path = Path(temp_dir) / "AGENTS.md"
            agents_content = "Original AGENTS content"
            agents_path.write_text(agents_content)

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


class TestInitWithAgentsMd:
    """Test the init command with AGENTS.md and CLAUDE.md creation."""

    def test_init_creates_agents_and_claude_md_by_default(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that AGENTS.md and CLAUDE.md are created by default during init."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
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
                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = temp_source
                mock_as_file.return_value.__exit__.return_value = None

                result = runner.invoke(cli, ["init"])

                assert result.exit_code == 0
                assert "AGENTS.md" in result.output

                assert os.path.exists("AGENTS.md")
                assert os.path.exists("CLAUDE.md")

                # Should NOT create .agent directory or .claude/commands/
                assert not os.path.exists(".agent")
                assert not os.path.exists(".claude/commands")

    def test_init_overwrites_existing_agents_md(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that existing AGENTS.md is overwritten."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

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
                mock_path = MagicMock()
                mock_files.return_value.joinpath.return_value = mock_path
                mock_as_file.return_value.__enter__.return_value = temp_source
                mock_as_file.return_value.__exit__.return_value = None

                result = runner.invoke(cli, ["init"])

                assert result.exit_code == 0

                with open("AGENTS.md", "r") as f:
                    content = f.read()
                    assert content != original_content
                    assert content == "Test content"
