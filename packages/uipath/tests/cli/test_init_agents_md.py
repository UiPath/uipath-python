"""Tests for AGENTS.md generation in the init command."""

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

    def test_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_source = Path(temp_dir) / "source.md"
            mock_source.write_text("Test content")

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
            ):
                mock_files.return_value.joinpath.return_value = MagicMock()
                mock_as_file.return_value.__enter__.return_value = mock_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_file(temp_dir, "AGENTS.md", False)

                assert (Path(temp_dir) / "AGENTS.md").read_text() == "Test content"

    def test_overwrites_existing_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "AGENTS.md"
            existing.write_text("original")

            mock_source = Path(temp_dir) / "source.md"
            mock_source.write_text("new content")

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
            ):
                mock_files.return_value.joinpath.return_value = MagicMock()
                mock_as_file.return_value.__enter__.return_value = mock_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_file(temp_dir, "AGENTS.md", False)

                assert existing.read_text() == "new content"

    def test_skips_existing_when_no_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "AGENTS.md"
            existing.write_text("original")

            generate_agent_md_file(temp_dir, "AGENTS.md", no_agents_md_override=True)

            assert existing.read_text() == "original"

    def test_handles_errors_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch("uipath._cli.cli_init.console") as mock_console,
            ):
                mock_files.side_effect = RuntimeError("boom")

                generate_agent_md_file(temp_dir, "AGENTS.md", False)

                mock_console.warning.assert_called_once()


class TestGenerateAgentMdFiles:
    """Test the generate_agent_md_files entry point."""

    def test_default_does_not_bundle_offline_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_source = Path(temp_dir) / "source.md"
            mock_source.write_text("Test content")

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
                patch("uipath._cli.cli_init.console"),
            ):
                mock_files.return_value.joinpath.return_value = MagicMock()
                mock_as_file.return_value.__enter__.return_value = mock_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_files(temp_dir, False)

                assert (Path(temp_dir) / "AGENTS.md").exists()
                assert (Path(temp_dir) / "CLAUDE.md").exists()
                assert not (Path(temp_dir) / ".uipath" / "llms-full.txt").exists()
                assert not (Path(temp_dir) / ".agent").exists()
                assert not (Path(temp_dir) / ".claude").exists()
                # default AGENTS.md must not reference the offline fallback
                assert (
                    ".uipath/llms-full.txt"
                    not in (Path(temp_dir) / "AGENTS.md").read_text()
                )

    def test_with_offline_docs_bundles_llms_full(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_source = Path(temp_dir) / "source.md"
            mock_source.write_text("# AGENTS\n\n1. step one\n2. step two\n")

            with (
                patch("uipath._cli.cli_init.importlib.resources.files") as mock_files,
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
                patch("uipath._cli.cli_init.console"),
            ):
                mock_files.return_value.joinpath.return_value = MagicMock()
                mock_as_file.return_value.__enter__.return_value = mock_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_files(temp_dir, False, with_offline_docs=True)

                assert (Path(temp_dir) / ".uipath" / "llms-full.txt").exists()
                agents_text = (Path(temp_dir) / "AGENTS.md").read_text()
                assert ".uipath/llms-full.txt" in agents_text

    def test_with_offline_docs_skips_when_resource_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_source = Path(temp_dir) / "source.md"
            mock_source.write_text("Test content")

            call_count = {"n": 0}

            def files_side_effect(_pkg: str):
                call_count["n"] += 1
                if call_count["n"] <= 2:  # AGENTS.md + CLAUDE.md
                    m = MagicMock()
                    m.joinpath.return_value = MagicMock()
                    return m
                raise FileNotFoundError("no llms-full.txt bundled")

            with (
                patch(
                    "uipath._cli.cli_init.importlib.resources.files",
                    side_effect=files_side_effect,
                ),
                patch(
                    "uipath._cli.cli_init.importlib.resources.as_file"
                ) as mock_as_file,
                patch("uipath._cli.cli_init.console"),
            ):
                mock_as_file.return_value.__enter__.return_value = mock_source
                mock_as_file.return_value.__exit__.return_value = None

                generate_agent_md_files(temp_dir, False, with_offline_docs=True)

                assert (Path(temp_dir) / "AGENTS.md").exists()
                assert not (Path(temp_dir) / ".uipath" / "llms-full.txt").exists()


class TestInitWithAgentsMd:
    """Test the init command end to end."""

    def _generate_pyproject(self) -> None:
        with open("pyproject.toml", "w") as f:
            f.write(
                '[project]\nname = "test-project"\nversion = "0.1.0"\n'
                'description = "Test"\nauthors = [{name = "Test"}]\n'
                'requires-python = ">=3.11"\n'
            )

    def test_init_creates_agents_md(self, runner: CliRunner, temp_dir: str) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            self._generate_pyproject()
            result = runner.invoke(cli, ["init"])

            assert result.exit_code == 0
            assert os.path.exists("AGENTS.md")
            assert os.path.exists("CLAUDE.md")
            assert not os.path.exists(".agent")
            assert not os.path.exists(".claude")

    def test_init_overwrites_existing_agents_md_by_default(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("main.py", "w") as f:
                f.write("def main(input): return input")
            with open("AGENTS.md", "w") as f:
                f.write("user content")

            self._generate_pyproject()
            result = runner.invoke(cli, ["init"])

            assert result.exit_code == 0
            with open("AGENTS.md") as f:
                assert f.read() != "user content"

    def test_init_preserves_agents_md_with_no_override(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("main.py", "w") as f:
                f.write("def main(input): return input")
            with open("AGENTS.md", "w") as f:
                f.write("user content")

            self._generate_pyproject()
            result = runner.invoke(cli, ["init", "--no-agents-md-override"])

            assert result.exit_code == 0
            with open("AGENTS.md") as f:
                assert f.read() == "user content"
