import json
import os
import re
import uuid
from importlib.metadata import version
from unittest.mock import patch

from click.testing import CliRunner
from packaging.specifiers import SpecifierSet

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult


class TestNew:
    def test_new_project_creation(self, runner: CliRunner, temp_dir: str) -> None:
        """Test project creation scenarios."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Test creating a new project
            result = runner.invoke(cli, ["new", "my_project"])
            assert result.exit_code == 0
            assert os.path.exists("main.py")
            assert os.path.exists("pyproject.toml")

    def test_new_project_writes_uipath_json_id(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """uipath.json gets a GUID id up front so later commands don't warn."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", "my_project"])
            assert result.exit_code == 0
            with open("uipath.json") as f:
                config = json.load(f)
            uuid.UUID(config["id"])
            assert config["functions"] == {"main": "main.py:main"}

    def test_new_project_without_name(self, runner: CliRunner, temp_dir: str) -> None:
        """Test creating a new project without specifying a name."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", ""])
            assert result.exit_code == 1
            assert "Please specify a name for your project" in result.output

    def test_new_project_with_existing_files(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test creating a new project when files already exist."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create existing files
            with open("main.py", "w") as f:
                f.write("print('Existing file')")

            result = runner.invoke(cli, ["new", "my_project"])
            assert result.exit_code == 0
            assert "Created 'main.py' file." in result.output

    def test_new_project_middleware_interaction(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test middleware integration during project creation."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                # Test middleware stopping execution with error
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=False,
                    error_message="Middleware error",
                    should_include_stacktrace=False,
                )

                result = runner.invoke(cli, ["new", "my_project"])
                assert result.exit_code == 1
                assert "Middleware error" in result.output
                assert not os.path.exists("main.py")

                # Test middleware allowing execution
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=True,
                    error_message=None,
                    should_include_stacktrace=False,
                )

                result = runner.invoke(cli, ["new", "my_project"])
                assert result.exit_code == 0
                assert os.path.exists("main.py")

    def test_new_project_error_handling(self, runner: CliRunner, temp_dir: str) -> None:
        """Test error handling in new command."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Mock middleware to allow execution
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                # Simulate an error during project creation
                with patch("uipath._cli.cli_new.generate_script") as mock_generate:
                    mock_generate.side_effect = Exception("Generation error")
                    result = runner.invoke(cli, ["new", "my_project"])
                    assert result.exit_code == 1
                    assert "Created 'main.py' file." not in result.output


class TestUipathDependencySpec:
    """The scaffolded pin must follow the installed uipath version."""

    def _written_pin(self, temp_dir: str) -> str:
        from uipath._cli.cli_new import generate_pyproject

        generate_pyproject(temp_dir, "demo")
        with open(os.path.join(temp_dir, "pyproject.toml")) as f:
            content = f.read()
        match = re.search(r'"(uipath[^"]*)"', content)
        assert match is not None, content
        return match.group(1)

    def test_pin_derived_from_installed_version(self, temp_dir: str) -> None:
        with patch("uipath._cli._get_safe_version", return_value="2.14.7"):
            assert self._written_pin(temp_dir) == "uipath>=2.14.0, <2.15.0"

    def test_pin_strips_prerelease_suffix(self, temp_dir: str) -> None:
        with patch("uipath._cli._get_safe_version", return_value="2.15.0rc1"):
            assert self._written_pin(temp_dir) == "uipath>=2.15.0, <2.16.0"

    def test_pin_falls_back_when_version_unknown(self, temp_dir: str) -> None:
        from uipath._cli.cli_new import _fallback_uipath_dependency_spec, console

        # _get_safe_version() returns "unknown" on PackageNotFoundError.
        with (
            patch("uipath._cli._get_safe_version", return_value="unknown"),
            patch.object(console, "warning") as mock_warning,
        ):
            assert self._written_pin(temp_dir) == _fallback_uipath_dependency_spec()
        mock_warning.assert_called_once()
        assert (
            "Could not determine the installed 'uipath' version"
            in (mock_warning.call_args.args[0])
        )

    def test_fallback_pin_admits_installed_uipath(self) -> None:
        """Guard: a release PR that forgets to bump FALLBACK_UIPATH_MINOR fails CI."""
        from uipath._cli.cli_new import _fallback_uipath_dependency_spec

        spec = _fallback_uipath_dependency_spec().removeprefix("uipath")
        installed = version("uipath")
        assert SpecifierSet(spec).contains(installed, prereleases=True), (
            f"fallback pin '{spec}' does not admit installed uipath {installed}; "
            "bump FALLBACK_UIPATH_MINOR in cli_new.py"
        )

    def test_scaffolded_pin_contains_installed_uipath(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Regression guard: runs against the real installed package, not a mock.

        A stale hard-coded range would make ``uv sync`` downgrade the project's
        venv right after ``uipath new``.
        """
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", "demo"])
            assert result.exit_code == 0
            with open("pyproject.toml") as f:
                content = f.read()
            match = re.search(r'"uipath([^"]*)"', content)
            assert match is not None, content
            pin = SpecifierSet(match.group(1))
            installed = version("uipath")
            assert pin.contains(installed, prereleases=True), (
                f"scaffolded pin '{pin}' does not contain installed uipath {installed}"
            )
