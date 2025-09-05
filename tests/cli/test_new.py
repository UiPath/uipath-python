import os
from unittest.mock import patch

from click.testing import CliRunner

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
