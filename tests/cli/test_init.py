import json
import os
from unittest.mock import patch

from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult


class TestInit:
    def test_init_env_file_creation(self, runner: CliRunner, temp_dir: str) -> None:
        """Test .env file creation scenarios."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Test creation of new .env
            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0
            assert "Created '.env' file" in result.output

            assert os.path.exists(".env")

            # Test existing .env isn't overwritten
            original_content = "EXISTING=CONFIG"
            with open(".env", "w") as f:
                f.write(original_content)

            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0
            with open(".env", "r") as f:
                assert f.read() == original_content

    def test_init_creates_empty_uipath_json(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that init creates an empty uipath.json with functions structure."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0
            assert os.path.exists("uipath.json")
            assert "Created 'uipath.json' file" in result.output

            # Verify uipath.json has correct empty structure
            with open("uipath.json", "r") as f:
                config = json.load(f)
                assert "functions" in config
                assert isinstance(config["functions"], dict)
                assert len(config["functions"]) == 0

    def test_init_with_existing_uipath_json(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test init when uipath.json already exists with functions."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create test script
            with open("main.py", "w") as f:
                f.write("def main(input: str) -> str: return input")

            # Create uipath.json with functions
            uipath_config = {"functions": {"main": "main.py:main"}}
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0

            # Should generate entry-points.json
            assert os.path.exists("entry-points.json")
            assert "Created 'entry-points.json' file" in result.output

            # Verify entry-points.json has correct structure
            with open("entry-points.json", "r") as f:
                entry_points = json.load(f)
                assert "entryPoints" in entry_points
                assert len(entry_points["entryPoints"]) == 1
                assert entry_points["entryPoints"][0]["filePath"] == "main"
                assert "uniqueId" in entry_points["entryPoints"][0]

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

                result = runner.invoke(cli, ["init"], env={})
                assert result.exit_code == 1
                assert "Middleware error" in result.output
                assert os.path.exists("uipath.json")

                # Test middleware allowing execution
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=True,
                    error_message=None,
                    should_include_stacktrace=False,
                )

                result = runner.invoke(cli, ["init"], env={})
                assert result.exit_code == 0
                assert os.path.exists("uipath.json")

    def test_init_error_handling(self, runner: CliRunner, temp_dir: str) -> None:
        """Test error handling in init command."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create invalid Python file
            with open("invalid.py", "w") as f:
                f.write("def main(input: return input")  # Invalid syntax

            # Create uipath.json with reference to invalid file
            uipath_config = {"functions": {"main": "invalid.py:main"}}
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            # Mock middleware to allow execution
            with patch("uipath._cli.cli_init.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(cli, ["init"], env={})

                # The command should fail due to invalid syntax
                assert result.exit_code == 1, (
                    f"Expected exit code 1, got {result.exit_code}. Output: {result.output}"
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

            # Create uipath.json with function reference
            uipath_config = {"functions": {"main": "test.py:main"}}
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0
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

    def test_schema_json_draft07_compliance(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that generated schemas comply with JSON Schema draft-07 specification."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a comprehensive test script with all supported types
            script_content = """
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel


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


class BoolEnum(int, Enum):
    FALSE_VALUE = 0
    TRUE_VALUE = 1


class NestedPydanticModel(BaseModel):
    nested_field: str
    nested_number: int


@dataclass
class NestedDataclass:
    nested_str: str
    nested_int: int


@dataclass
class Input:
    string_field: str
    integer_field: int
    float_field: float
    boolean_field: bool
    list_of_strings: List[str]
    list_of_integers: List[int]
    dict_field: Dict[str, str]
    optional_string: Optional[str]
    optional_int: Optional[int]
    optional_list: Optional[List[str]]
    string_enum_field: StringEnum
    int_enum_field: IntEnum
    float_enum_field: FloatEnum
    bool_enum_field: BoolEnum
    pydantic_nested: NestedPydanticModel
    dataclass_nested: NestedDataclass
    list_of_objects: List[NestedDataclass]
    nested_list: List[List[str]]
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

            # Create uipath.json with function reference
            uipath_config = {"functions": {"main": "comprehensive_types.py:main"}}
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            # Run init command
            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0
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

            # Test basic types
            assert props["string_field"]["type"] == "string"
            assert props["integer_field"]["type"] == "integer"
            assert props["float_field"]["type"] == "number"
            assert props["boolean_field"]["type"] == "boolean"

            # Test collections
            assert props["list_of_strings"]["type"] == "array"
            assert props["list_of_strings"]["items"]["type"] == "string"
            assert props["list_of_integers"]["type"] == "array"
            assert props["list_of_integers"]["items"]["type"] == "integer"
            assert props["dict_field"]["type"] == "object"

            # Test Optional types
            assert props["optional_string"]["type"] == "string"
            assert props["optional_int"]["type"] == "integer"
            assert props["optional_list"]["type"] == "array"

            # Test Enum types
            assert props["string_enum_field"]["type"] == "string"
            assert set(props["string_enum_field"]["enum"]) == {
                "option_a",
                "option_b",
                "option_c",
            }
            assert props["int_enum_field"]["type"] == "integer"
            assert set(props["int_enum_field"]["enum"]) == {1, 2, 3}
            assert props["float_enum_field"]["type"] == "number"
            assert set(props["float_enum_field"]["enum"]) == {3.14, 2.71, 1.618}

            # Test nested objects
            assert props["pydantic_nested"]["type"] == "object"
            assert props["dataclass_nested"]["type"] == "object"

            # Test required fields
            assert "string_field" in required
            assert "optional_with_default" not in required
            assert "int_with_default" not in required

            # Validate output schema
            assert output_schema["type"] == "object"
            assert output_schema["properties"]["result"]["type"] == "string"
            assert output_schema["properties"]["success"]["type"] == "boolean"

    def test_bindings_and_entrypoints_files_creation(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test that bindings.json and entry-points.json files are created correctly."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create a simple Python file
            with open("main.py", "w") as f:
                f.write("def main(input: str) -> str: return input")

            # Create uipath.json with function
            uipath_config = {"functions": {"main": "main.py:main"}}
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0
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

            # Verify uipath.json still has functions
            with open("uipath.json", "r") as f:
                config = json.load(f)
                assert "functions" in config
                assert config["functions"]["main"] == "main.py:main"
