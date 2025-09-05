import json
import os
import re
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult


@pytest.fixture
def bindings_script() -> str:
    if os.path.isfile("mocks/bindings_script.py"):
        with open("mocks/bindings_script.py", "r") as file:
            data = file.read()
    else:
        with open("tests/cli/mocks/bindings_script.py", "r") as file:
            data = file.read()
    return data


class TestInit:
    def test_init_env_file_creation(self, runner: CliRunner, temp_dir: str) -> None:
        """Test .env file creation scenarios."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("main.py", "w") as f:
                f.write("def main(input): return input")
            # Test creation of new .env
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert "Created '.env' file" in result.output

            assert os.path.exists(".env")

            # Test existing .env isn't overwritten
            original_content = "EXISTING=CONFIG"
            with open(".env", "w") as f:
                f.write(original_content)

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            with open(".env", "r") as f:
                assert f.read() == original_content

    def test_init_script_detection(self, runner: CliRunner, temp_dir: str) -> None:
        """Test Python script detection scenarios."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Test empty directory
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 1
            assert "No python files found in the current directory" in result.output

            # Test single Python file
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert os.path.exists("uipath.json")

            # Test multiple Python files
            with open("second.py", "w") as f:
                f.write("def main(input): return input")

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 1
            assert (
                "Multiple python files found in the current directory" in result.output
            )
            assert "Please specify the entrypoint" in result.output

    def test_init_with_entrypoint(self, runner: CliRunner, temp_dir: str) -> None:
        """Test init with specified entrypoint."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Test with non-existent file
            result = runner.invoke(cli, ["init", "nonexistent.py"])
            assert result.exit_code == 1
            assert "does not exist in the current directory" in result.output

            # Test with valid Python file
            with open("script.py", "w") as f:
                f.write("def main(input): return input")

            result = runner.invoke(cli, ["init", "script.py"])
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

    def test_init_middleware_interaction(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test middleware integration."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_init.Middlewares.next") as mock_middleware:
                # Test middleware stopping execution with error
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=False,
                    error_message="Middleware error",
                    should_include_stacktrace=False,
                )

                result = runner.invoke(cli, ["init"])
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

                result = runner.invoke(cli, ["init"])
                assert result.exit_code == 0
                assert os.path.exists("uipath.json")

    def test_init_error_handling(self, runner: CliRunner, temp_dir: str) -> None:
        """Test error handling in init command."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Test invalid Python syntax
            with open("invalid.py", "w") as f:
                f.write("def main(input: return input")  # Invalid syntax

            # Mock middleware to allow execution
            with patch("uipath._cli.cli_init.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(cli, ["init", "invalid.py"])
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
                    mock_middleware.return_value = MiddlewareResult(
                        should_continue=True
                    )

                    result = runner.invoke(cli, ["init", "script.py"])
                    assert result.exit_code == 1
                    # Use regex to match any spinner character followed by the expected message
                    assert re.search(
                        r"⠋|⠼|⠇|⠏|⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏ Initializing UiPath project \.\.\.❌ Error creating configuration file:\n Generation error\n",
                        result.output,
                    )

    def test_init_config_generation(self, runner: CliRunner, temp_dir: str) -> None:
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

            result = runner.invoke(cli, ["init", "test.py"])
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

    def test_bindings_inference(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        bindings_script: str,
    ) -> None:
        """Test the inference of UiPath bindings from the code."""

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open(".env", "w") as f:
                for key, value in mock_env_vars.items():
                    f.write(f"{key}={value}\n")

            with open("bindings.py", "w") as f:
                f.write(bindings_script)
            print(1)
            result = runner.invoke(cli, ["init", "bindings.py"])
            assert result.exit_code == 0
            assert "Created 'uipath.json' file" in result.output
            assert os.path.exists("uipath.json")
            with open("uipath.json", "r") as f:
                config = json.load(f)
                assert "bindings" in config
                bindings = config["bindings"]
                assert len(bindings) > 0
                assert "resources" in config["bindings"]
                resources = config["bindings"]["resources"]
                assert len(resources) == 12

                # Helper function to find resource by key
                def find_resource(key: str) -> dict[str, Any]:
                    return next((r for r in resources if r["key"] == key), {})

                assert all(r["metadata"]["BindingsVersion"] == "2.2" for r in resources)

                # Test resources with and without async for each type
                retrieve_resource_types = ["asset", "bucket", "index"]
                for resource_type in retrieve_resource_types:
                    # Test async variant
                    async_key = f"{resource_type}_from_retrieve_async"
                    async_resource = find_resource(async_key)
                    assert async_resource["resource"] == resource_type
                    assert (
                        async_resource["metadata"]["ActivityName"] == "retrieve_async"
                    )
                    assert async_resource["value"]["name"]["defaultValue"] == async_key
                    assert "folderPath" not in async_resource["value"]

                    # Test non-async variant
                    non_async_key = f"{resource_type}_from_retrieve"
                    non_async_resource = find_resource(non_async_key)
                    assert non_async_resource["resource"] == resource_type
                    assert non_async_resource["metadata"]["ActivityName"] == "retrieve"
                    assert (
                        non_async_resource["value"]["name"]["defaultValue"]
                        == non_async_key
                    )
                    assert "folderPath" not in non_async_resource["value"]

                    # Test folder path variant
                    folder_key = (
                        f"{resource_type}_folder_path.{resource_type}_with_folder_path"
                    )
                    folder_resource = find_resource(folder_key)
                    assert folder_resource["resource"] == resource_type
                    assert folder_resource["metadata"]["ActivityName"] == "retrieve"
                    assert (
                        folder_resource["value"]["folderPath"]["defaultValue"]
                        == f"{resource_type}_folder_path"
                    )
                    assert (
                        folder_resource["value"]["name"]["defaultValue"]
                        == f"{resource_type}_with_folder_path"
                    )

                # Test process resources
                # Test async variant
                process_async = find_resource("process_name_from_invoke_async")
                assert process_async["resource"] == "process"
                assert process_async["metadata"]["ActivityName"] == "invoke_async"
                assert (
                    process_async["value"]["name"]["defaultValue"]
                    == "process_name_from_invoke_async"
                )
                assert "folderPath" not in process_async["value"]

                # Test non-async variant
                process_non_async = find_resource("process_name_from_invoke")
                assert process_non_async["resource"] == "process"
                assert process_non_async["metadata"]["ActivityName"] == "invoke"
                assert (
                    process_non_async["value"]["name"]["defaultValue"]
                    == "process_name_from_invoke"
                )
                assert "folderPath" not in process_non_async["value"]

                # Test folder path variant
                process_folder = find_resource(
                    "process_folder_path.process_with_folder_path"
                )
                assert process_folder["resource"] == "process"
                assert process_folder["metadata"]["ActivityName"] == "invoke"
                assert (
                    process_folder["value"]["folderPath"]["defaultValue"]
                    == "process_folder_path"
                )
                assert (
                    process_folder["value"]["name"]["defaultValue"]
                    == "process_with_folder_path"
                )

                # Verify common metadata fields
                for resource in resources:
                    assert "metadata" in resource
                    assert "DisplayLabel" in resource["metadata"]
                    assert resource["metadata"]["DisplayLabel"] == "FullName"
                    assert "value" in resource
                    if "folderPath" in resource["value"]:
                        assert (
                            resource["value"]["folderPath"]["displayName"]
                            == "Folder Path"
                        )
                        assert not resource["value"]["folderPath"]["isExpression"]
                    assert resource["value"]["name"]["displayName"] == "Name"
                    assert not resource["value"]["name"]["isExpression"]
