import json
import os
import re
from unittest.mock import patch

from click.testing import CliRunner

from uipath._cli.cli_init import init  # type: ignore
from uipath._cli.middlewares import MiddlewareResult


def test_init_env_file_creation(runner: CliRunner, temp_dir: str) -> None:
    """Test .env file creation scenarios."""
    with runner.isolated_filesystem(temp_dir=temp_dir):
        with open("main.py", "w") as f:
            f.write("def main(input): return input")
        # Test creation of new .env
        result = runner.invoke(init)
        assert result.exit_code == 0
        assert "Created '.env' file" in result.output

        assert os.path.exists(".env")

        # Test existing .env isn't overwritten
        original_content = "EXISTING=CONFIG"
        with open(".env", "w") as f:
            f.write(original_content)

        result = runner.invoke(init)
        assert result.exit_code == 0
        with open(".env", "r") as f:
            assert f.read() == original_content


def test_init_script_detection(runner: CliRunner, temp_dir: str) -> None:
    """Test Python script detection scenarios."""
    with runner.isolated_filesystem(temp_dir=temp_dir):
        # Test empty directory
        result = runner.invoke(init)
        assert result.exit_code == 1
        assert "No python files found in the current directory" in result.output

        # Test single Python file
        with open("main.py", "w") as f:
            f.write("def main(input): return input")

        result = runner.invoke(init)
        assert result.exit_code == 0
        assert os.path.exists("uipath.json")

        # Test multiple Python files
        with open("second.py", "w") as f:
            f.write("def main(input): return input")

        result = runner.invoke(init)
        assert result.exit_code == 1
        assert "Multiple python files found in the current directory" in result.output
        assert "Please specify the entrypoint" in result.output


def test_init_with_entrypoint(runner: CliRunner, temp_dir: str) -> None:
    """Test init with specified entrypoint."""
    with runner.isolated_filesystem(temp_dir=temp_dir):
        # Test with non-existent file
        result = runner.invoke(init, ["nonexistent.py"])
        assert result.exit_code == 1
        assert "does not exist in the current directory" in result.output

        # Test with valid Python file
        with open("script.py", "w") as f:
            f.write("def main(input): return input")

        result = runner.invoke(init, ["script.py"])
        assert result.exit_code == 0
        assert os.path.exists("uipath.json")

        # Verify config content
        with open("uipath.json", "r") as f:
            config = json.load(f)
            assert "entryPoints" in config
            assert len(config["entryPoints"]) == 1
            assert config["entryPoints"][0]["filePath"] == "script.py"
            assert config["entryPoints"][0]["type"] == "agent"
            assert "uniqueId" in config["entryPoints"][0]


def test_init_middleware_interaction(runner: CliRunner, temp_dir: str) -> None:
    """Test middleware integration."""
    with runner.isolated_filesystem(temp_dir=temp_dir):
        with patch("uipath._cli.cli_init.Middlewares.next") as mock_middleware:
            # Test middleware stopping execution with error
            mock_middleware.return_value = MiddlewareResult(
                should_continue=False,
                error_message="Middleware error",
                should_include_stacktrace=False,
            )

            result = runner.invoke(init)
            assert result.exit_code == 1
            assert "Middleware error" in result.output
            assert not os.path.exists("uipath.json")

            # Test middleware allowing execution
            mock_middleware.return_value = MiddlewareResult(
                should_continue=True,
                error_message=None,
                should_include_stacktrace=False,
            )

            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            result = runner.invoke(init)
            assert result.exit_code == 0
            assert os.path.exists("uipath.json")


def test_init_error_handling(runner: CliRunner, temp_dir: str) -> None:
    """Test error handling in init command."""
    with runner.isolated_filesystem(temp_dir=temp_dir):
        # Test invalid Python syntax
        with open("invalid.py", "w") as f:
            f.write("def main(input: return input")  # Invalid syntax

        # Mock middleware to allow execution
        with patch("uipath._cli.cli_init.Middlewares.next") as mock_middleware:
            mock_middleware.return_value = MiddlewareResult(should_continue=True)

            result = runner.invoke(init, ["invalid.py"])
            assert result.exit_code == 1
            assert "Error creating configuration" in result.output
            assert "invalid syntax" in result.output  # Should show stacktrace

        # Test with generate_args raising exception
        with patch("uipath._cli.cli_init.generate_args") as mock_generate:
            mock_generate.side_effect = Exception("Generation error")
            with open("script.py", "w") as f:
                f.write("def main(input): return input")

            # Mock middleware to allow execution
            with patch("uipath._cli.cli_init.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(init, ["script.py"])
                assert result.exit_code == 1
                # Use regex to match any spinner character followed by the expected message
                assert re.search(
                    r"⠋|⠼|⠇|⠏|⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏ Initializing UiPath project \.\.\.❌ Error creating configuration file:\n Generation error\n",
                    result.output,
                )


def test_init_config_generation(runner: CliRunner, temp_dir: str) -> None:
    """Test configuration file generation with different input/output schemas."""
    with runner.isolated_filesystem(temp_dir=temp_dir):
        # Create test script with typed input/output
        script_content = """
from dataclasses import dataclass
from typing import Optional

@dataclass
class Input:
    message: str
    count: Optional[int] = None

@dataclass
class Output:
    result: str

def main(input: Input) -> Output:
    return Output(result=input.message)
"""
        with open("test.py", "w") as f:
            f.write(script_content)

        result = runner.invoke(init, ["test.py"])
        assert result.exit_code == 0
        assert os.path.exists("uipath.json")

        with open("uipath.json", "r") as f:
            config = json.load(f)
            entry = config["entryPoints"][0]

            # Verify input schema
            assert "input" in entry
            input_schema = entry["input"]
            assert "message" in input_schema["properties"]
            assert "count" in input_schema["properties"]
            assert "message" in input_schema["required"]

            # Verify output schema
            assert "output" in entry
            output_schema = entry["output"]
            assert "result" in output_schema["properties"]
