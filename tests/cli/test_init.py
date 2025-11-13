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
            assert os.path.exists("entry-points.json")

            # Verify config content
            with open("entry-points.json", "r") as f:
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
            with patch("uipath._cli._runtime._runtime.generate_args") as mock_generate:
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
            assert os.path.exists("entry-points.json")

            with open("entry-points.json", "r") as f:
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
            result = runner.invoke(cli, ["init", "bindings.py"])
            assert result.exit_code == 0
            assert "Created 'uipath.json' file" in result.output
            assert "Created 'bindings.json' file" in result.output
            assert os.path.exists("uipath.json")
            assert os.path.exists("bindings.json")

            # Verify uipath.json doesn't have bindings
            with open("uipath.json", "r") as f:
                config = json.load(f)
                assert "bindings" not in config

            # Verify bindings are in separate file
            with open("bindings.json", "r") as f:
                bindings_data = json.load(f)
                assert "version" in bindings_data
                assert bindings_data["version"] == "2.0"
                assert "resources" in bindings_data
                resources = bindings_data["resources"]
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
                        f"{resource_type}_with_folder_path.{resource_type}_folder_path"
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
                    "process_with_folder_path.process_folder_path"
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

    def test_schema_json_draft07_compliance(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that generated schemas comply with JSON Schema draft-07 specification.

        This test validates all supported types are correctly converted to their
        JSON Schema draft-07 equivalents.
        """
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a comprehensive test script with all supported types
            script_content = """
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel


# Enum types for testing
class StringEnum(str, Enum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"
    OPTION_C = "option_c"


class IntEnum(int, Enum):
    ONE = 1
    TWO = 2
    THREE = 3


class FloatEnum(float, Enum):
    PI = 3.14
    E = 2.71
    GOLDEN = 1.618


class BoolEnum(int, Enum):  # Python bools are ints
    FALSE_VALUE = 0
    TRUE_VALUE = 1


# Nested Pydantic model for testing
class NestedPydanticModel(BaseModel):
    nested_field: str
    nested_number: int


# Nested dataclass for testing
@dataclass
class NestedDataclass:
    nested_str: str
    nested_int: int


# Main Input class with all types
@dataclass
class Input:
    # Basic types
    string_field: str
    integer_field: int
    float_field: float
    boolean_field: bool

    # Collections
    list_of_strings: List[str]
    list_of_integers: List[int]
    dict_field: Dict[str, str]

    # Optional types
    optional_string: Optional[str]
    optional_int: Optional[int]
    optional_list: Optional[List[str]]

    # Enum types
    string_enum_field: StringEnum
    int_enum_field: IntEnum
    float_enum_field: FloatEnum
    bool_enum_field: BoolEnum

    # Nested objects
    pydantic_nested: NestedPydanticModel
    dataclass_nested: NestedDataclass

    # Complex nested types
    list_of_objects: List[NestedDataclass]
    nested_list: List[List[str]]

    # Optional fields (with defaults)
    optional_with_default: Optional[str] = None
    int_with_default: int = 42


@dataclass
class Output:
    result: str
    success: bool


def main(input: Input) -> Output:
    return Output(result="test", success=True)
"""
            with open("comprehensive_types.py", "w") as f:
                f.write(script_content)

            # Run init command
            result = runner.invoke(cli, ["init", "comprehensive_types.py"])
            assert result.exit_code == 0
            assert os.path.exists("uipath.json")
            assert os.path.exists("entry-points.json")

            # Load and validate the generated config
            with open("entry-points.json", "r") as f:
                config = json.load(f)
                entry = config["entryPoints"][0]
                input_schema = entry["input"]
                output_schema = entry["output"]

            # Validate top-level structure
            assert input_schema["type"] == "object"
            assert "properties" in input_schema
            assert "required" in input_schema

            props = input_schema["properties"]
            required = input_schema["required"]

            # Test basic types - JSON Schema draft-07 compliance
            assert props["string_field"]["type"] == "string"
            assert props["integer_field"]["type"] == "integer"
            assert (
                props["float_field"]["type"] == "number"
            )  # draft-07 uses "number" not "double"
            assert props["boolean_field"]["type"] == "boolean"

            # Test collections
            assert props["list_of_strings"]["type"] == "array"
            assert "items" in props["list_of_strings"]
            assert props["list_of_strings"]["items"]["type"] == "string"

            assert props["list_of_integers"]["type"] == "array"
            assert props["list_of_integers"]["items"]["type"] == "integer"

            assert props["dict_field"]["type"] == "object"

            # Test Optional types (should have the underlying type, not Union)
            assert props["optional_string"]["type"] == "string"
            assert props["optional_int"]["type"] == "integer"
            assert props["optional_list"]["type"] == "array"
            assert props["optional_list"]["items"]["type"] == "string"

            # Test Enum types with proper type inference
            assert props["string_enum_field"]["type"] == "string"
            assert "enum" in props["string_enum_field"]
            assert set(props["string_enum_field"]["enum"]) == {
                "option_a",
                "option_b",
                "option_c",
            }

            assert props["int_enum_field"]["type"] == "integer"
            assert "enum" in props["int_enum_field"]
            assert set(props["int_enum_field"]["enum"]) == {1, 2, 3}

            assert props["float_enum_field"]["type"] == "number"
            assert "enum" in props["float_enum_field"]
            assert set(props["float_enum_field"]["enum"]) == {3.14, 2.71, 1.618}

            assert props["bool_enum_field"]["type"] == "integer"
            assert "enum" in props["bool_enum_field"]
            assert set(props["bool_enum_field"]["enum"]) == {0, 1}

            # Test nested Pydantic model
            assert props["pydantic_nested"]["type"] == "object"
            assert "properties" in props["pydantic_nested"]
            assert "required" in props["pydantic_nested"]
            assert (
                props["pydantic_nested"]["properties"]["nested_field"]["type"]
                == "string"
            )
            assert (
                props["pydantic_nested"]["properties"]["nested_number"]["type"]
                == "integer"
            )
            assert set(props["pydantic_nested"]["required"]) == {
                "nested_field",
                "nested_number",
            }

            # Test nested dataclass
            assert props["dataclass_nested"]["type"] == "object"
            assert "properties" in props["dataclass_nested"]
            assert "required" in props["dataclass_nested"]
            assert (
                props["dataclass_nested"]["properties"]["nested_str"]["type"]
                == "string"
            )
            assert (
                props["dataclass_nested"]["properties"]["nested_int"]["type"]
                == "integer"
            )
            assert set(props["dataclass_nested"]["required"]) == {
                "nested_str",
                "nested_int",
            }

            # Test complex nested types
            assert props["list_of_objects"]["type"] == "array"
            assert props["list_of_objects"]["items"]["type"] == "object"
            assert "properties" in props["list_of_objects"]["items"]

            assert props["nested_list"]["type"] == "array"
            assert props["nested_list"]["items"]["type"] == "array"
            assert props["nested_list"]["items"]["items"]["type"] == "string"

            # Test required fields (fields without defaults should be required)
            # Fields with defaults should not be in required array
            assert "string_field" in required
            assert "integer_field" in required
            assert "float_field" in required
            assert "boolean_field" in required
            assert "optional_with_default" not in required
            assert "int_with_default" not in required

            # Validate output schema
            assert output_schema["type"] == "object"
            assert "properties" in output_schema
            assert "required" in output_schema
            assert output_schema["properties"]["result"]["type"] == "string"
            assert output_schema["properties"]["success"]["type"] == "boolean"
            assert set(output_schema["required"]) == {"result", "success"}

    def test_bindings_and_entrypoints_files_creation(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that bindings.json file is created correctly during init."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a simple Python file
            with open("main.py", "w") as f:
                f.write("def main(input): return input")

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert "Created 'uipath.json' file" in result.output
            assert "Created 'bindings.json' file" in result.output
            assert "Created 'entry-points.json' file" in result.output

            assert os.path.exists("bindings.json")
            assert os.path.exists("entry-points.json")

            # Verify bindings.json has correct structure
            with open("bindings.json", "r") as f:
                bindings_data = json.load(f)
                assert "version" in bindings_data
                assert bindings_data["version"] == "2.0"
                assert "resources" in bindings_data
                assert isinstance(bindings_data["resources"], list)

            # Verify uipath.json does NOT contain bindings and entryPoints
            with open("uipath.json", "r") as f:
                config = json.load(f)
                assert "bindings" not in config
                assert "entryPoints" not in config
