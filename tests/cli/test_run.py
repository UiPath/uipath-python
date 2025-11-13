# type: ignore
import os
from unittest import mock
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tests.cli.utils.uipath_json import UiPathJson
from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult


@pytest.fixture
def entrypoint():
    return "entrypoint.py"


@pytest.fixture
def simple_script() -> str:
    if os.path.isfile("mocks/simple_script.py"):
        with open("mocks/simple_script.py", "r") as file:
            data = file.read()
    else:
        with open("tests/cli/mocks/simple_script.py", "r") as file:
            data = file.read()
    return data


@pytest.fixture
def mock_env_vars():
    return {
        "UIPATH_CONFIG_PATH": "test_config.json",
        "UIPATH_JOB_KEY": "test-job-id",
        "UIPATH_TRACE_ID": "test-trace-id",
        "UIPATH_TRACING_ENABLED": "true",
        "UIPATH_PARENT_SPAN_ID": "test-parent-span",
        "UIPATH_ROOT_SPAN_ID": "test-root-span",
        "UIPATH_ORGANIZATION_ID": "test-org-id",
        "UIPATH_TENANT_ID": "test-tenant-id",
        "UIPATH_PROCESS_UUID": "test-process-id",
        "UIPATH_FOLDER_KEY": "test-folder-key",
        "LOG_LEVEL": "DEBUG",
    }


class TestRun:
    class TestFileInput:
        def test_run_input_file_not_found(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            with runner.isolated_filesystem(temp_dir=temp_dir):
                file_path = os.path.join(temp_dir, entrypoint)
                with open(file_path, "w") as f:
                    f.write("script content")
                result = runner.invoke(
                    cli, ["run", entrypoint, "--file", "not-here.json"]
                )
                assert result.exit_code != 0
                assert "Error: Invalid value for '-f' / '--file'" in result.output

        def test_run_invalid_input_file(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            file_name = "not-json.txt"
            with runner.isolated_filesystem(temp_dir=temp_dir):
                script_file_path = os.path.join(temp_dir, entrypoint)
                with open(script_file_path, "w") as f:
                    f.write("script content")
                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, "w") as f:
                    f.write("file content")
                result = runner.invoke(
                    cli, ["run", script_file_path, "--file", file_path]
                )
                assert result.exit_code == 1
                assert "Invalid Input File Extension" in result.output

        def test_run_input_file_success(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            file_name = "input.json"
            json_content = """
            {
                "input_key": "input_value"
            }"""

            with runner.isolated_filesystem(temp_dir=temp_dir):
                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, "w") as f:
                    f.write(json_content)
                with patch("uipath._cli.cli_run.Middlewares.next") as mock_middleware:
                    mock_middleware.return_value = MiddlewareResult(
                        should_continue=False,
                        info_message="Execution succeeded",
                        error_message=None,
                        should_include_stacktrace=False,
                    )
                    result = runner.invoke(
                        cli, ["run", entrypoint, "--file", file_path]
                    )
                    assert result.exit_code == 0
                    assert "Successful execution." in result.output
                    assert mock_middleware.call_count == 1
                    assert mock_middleware.call_args == mock.call(
                        "run",
                        entrypoint,
                        "{}",
                        False,
                        input_file=file_path,
                        debug=False,
                        debug_port=5678,
                        execution_output_file=None,
                        trace_file=None,
                    )

    class TestMiddleware:
        def test_no_entrypoint(self, runner: CliRunner, temp_dir: str):
            with runner.isolated_filesystem(temp_dir=temp_dir):
                result = runner.invoke(cli, ["run"])
                assert result.exit_code == 1
                assert (
                    "No entrypoint specified. Please provide a path to a Python script."
                    in result.output
                )

        def test_script_not_found(
            self, runner: CliRunner, temp_dir: str, entrypoint: str
        ):
            with runner.isolated_filesystem(temp_dir=temp_dir):
                result = runner.invoke(cli, ["run", entrypoint])
                assert result.exit_code == 1
                assert f"Script not found at path {entrypoint}" in result.output

        @pytest.mark.parametrize(
            "uipath_json_legacy", ["uipath-simple-script-mock.json"], indirect=True
        )
        def test_successful_execution(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
            mock_env_vars: dict,
            uipath_json_legacy: UiPathJson,
            simple_script: str,
        ):
            input_file_name = "input.json"
            output_file_name = "output.json"
            input_json_content = """
            {
                "message": "Hello world",
                "repeat": 2
            }"""
            with runner.isolated_filesystem(temp_dir=temp_dir):
                # create input file
                input_file_path = os.path.join(temp_dir, input_file_name)
                output_file_path = os.path.join(temp_dir, output_file_name)
                with open(input_file_path, "w") as f:
                    f.write(input_json_content)
                # Create test script
                script_file_path = os.path.join(temp_dir, entrypoint)
                with open(script_file_path, "w") as f:
                    f.write(simple_script)
                # create uipath.json
                with open("uipath.json", "w") as f:
                    f.write(uipath_json_legacy.to_json())
                result = runner.invoke(
                    cli,
                    [
                        "run",
                        script_file_path,
                        "--input-file",
                        input_file_path,
                        "--output-file",
                        output_file_path,
                    ],
                )
                assert result.exit_code == 0
                assert "Successful execution." in result.output
                assert result.output.count("Hello world") == 2
                assert os.path.exists(output_file_path)
                with open(output_file_path, "r") as f:
                    output = f.read()
                    assert output.count("Hello world") == 2

    def test_no_main_function_found(
        self,
        runner: CliRunner,
        temp_dir: str,
        entrypoint: str,
        mock_env_vars: dict,
        uipath_json_legacy: UiPathJson,
    ):
        input_file_name = "input.json"
        input_json_content = """
                {
                    "message": "Hello world",
                    "repeat": 2
                }"""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # create input file
            input_file_path = os.path.join(temp_dir, input_file_name)
            with open(input_file_path, "w") as f:
                f.write(input_json_content)
            # Create test script
            script_file_path = os.path.join(temp_dir, entrypoint)
            with open(script_file_path, "w") as f:
                f.write("print(0)")
            # create uipath.json
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            result = runner.invoke(cli, ["run", script_file_path, "{}"])
            assert result.exit_code == 1
            assert "No main function (main, run, or execute)" in result.output
            assert "Successful execution." not in result.output

    def test_middleware_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        entrypoint: str,
        mock_env_vars: dict,
        uipath_json_legacy: UiPathJson,
    ):
        input_file_name = "input.json"
        input_json_content = """
                {
                    "message": "Hello world",
                    "repeat": 2
                }"""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # create input file
            input_file_path = os.path.join(temp_dir, input_file_name)
            with open(input_file_path, "w") as f:
                f.write(input_json_content)
            # Create test script
            script_file_path = os.path.join(temp_dir, entrypoint)
            with open(script_file_path, "w") as f:
                f.write("print(0)")
            # create uipath.json
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with patch("uipath._cli.cli_run.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=False,
                    info_message="Execution failed",
                    error_message="some error message",
                    should_include_stacktrace=True,
                )
                result = runner.invoke(cli, ["run", script_file_path, "{}"])
            assert result.exit_code == 1
            assert "some error message" in result.output
            assert "Successful execution." not in result.output

    def test_pydantic_model_execution(
        self,
        runner: CliRunner,
        temp_dir: str,
        entrypoint: str,
        mock_env_vars: dict,
        uipath_json_legacy: UiPathJson,
    ):
        """Test successful execution with Pydantic models."""
        pydantic_script = """
from typing import Optional
from pydantic import BaseModel, Field


class PersonIn(BaseModel):
    name: str
    age: int
    email: Optional[str] = None


class PersonOut(BaseModel):
    name: str
    age: int
    email: Optional[str] = None
    is_adult: bool
    greeting: str


def main(input_data: PersonIn) -> PersonOut:
    return PersonOut(
        name=input_data.name,
        age=input_data.age,
        email=input_data.email,
        is_adult=input_data.age >= 18,
        greeting=f"Hello, {input_data.name}!"
    )
"""

        input_file_name = "input.json"
        output_file_name = "output.json"
        input_json_content = """
        {
            "name": "John Doe",
            "age": 25,
            "email": "john@example.com"
        }"""

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # create input file
            input_file_path = os.path.join(temp_dir, input_file_name)
            output_file_path = os.path.join(temp_dir, output_file_name)
            with open(input_file_path, "w") as f:
                f.write(input_json_content)
            # Create test script
            script_file_path = os.path.join(temp_dir, entrypoint)
            with open(script_file_path, "w") as f:
                f.write(pydantic_script)
            # create uipath.json
            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())

            result = runner.invoke(
                cli,
                [
                    "run",
                    script_file_path,
                    "--input-file",
                    input_file_path,
                    "--output-file",
                    output_file_path,
                ],
            )

            assert result.exit_code == 0
            assert "Successful execution." in result.output
            assert os.path.exists(output_file_path)

            with open(output_file_path, "r") as f:
                import json

                output_data = json.load(f)
                assert output_data["name"] == "John Doe"
                assert output_data["age"] == 25
                assert output_data["email"] == "john@example.com"
                assert output_data["is_adult"] is True
                assert output_data["greeting"] == "Hello, John Doe!"
