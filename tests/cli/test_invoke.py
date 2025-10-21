import json
import os
import urllib.parse
import uuid
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pytest_httpx import HTTPXMock

from tests.cli.utils.project_details import ProjectDetails
from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult


@pytest.fixture
def entrypoint():
    return "entrypoint.py"


def _create_env_file(mock_env_vars: dict[str, str]):
    """Create the environment file."""
    with open(".env", "w") as f:
        for key, value in mock_env_vars.items():
            f.write(f"{key}={value}\n")


class TestInvoke:
    class TestFileInput:
        def test_invoke_input_file_not_found(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            with runner.isolated_filesystem(temp_dir=temp_dir):
                result = runner.invoke(
                    cli, ["invoke", entrypoint, "--file", "not-here.json"]
                )
                assert result.exit_code != 0
                assert "Error: Invalid value for '-f' / '--file'" in result.output

        def test_invoke_invalid_input_file(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            file_name = "not-json.txt"
            with runner.isolated_filesystem(temp_dir=temp_dir):
                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, "w") as f:
                    f.write("file content")
                result = runner.invoke(cli, ["invoke", entrypoint, "--file", file_path])
                assert result.exit_code == 1
                assert "Input file extension must be '.json'." in result.output

    def test_invoke_successful(
        self,
        runner: CliRunner,
        temp_dir: str,
        entrypoint: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
        project_details: ProjectDetails,
    ):
        base_url = mock_env_vars.get("UIPATH_URL")
        job_key = uuid.uuid4()
        my_workspace_folder_id = "123"
        my_workspace_feed_id = "042e669a-c95f-46a3-87b0-9e5a98d7cf8a"
        release_id = "123"
        odata_top_filter = 25
        personal_workspace_response_data = {
            "PersonalWorskpaceFeedId": my_workspace_feed_id,
            "PersonalWorkspace": {"Id": my_workspace_folder_id},
        }
        list_release_response_data = {
            "value": [
                {
                    "ProcessVersion": project_details.version,
                    "Id": release_id,
                    "Key": "9d17b737-1283-4ebe-b1f5-7d88967b94e4",
                }
            ]
        }
        start_job_response_data = {
            "value": [{"Key": f"{job_key}", "other_key": "other_value"}]
        }
        # mock get release info
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases?$select=Id,Key,ProcessVersion&$top={odata_top_filter}&$filter=ProcessKey%20eq%20%27{urllib.parse.quote(project_details.name)}%27",
            status_code=200,
            text=json.dumps(list_release_response_data),
        )
        # mock get personal workspace info
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended?$expand=PersonalWorkspace",
            status_code=200,
            text=json.dumps(personal_workspace_response_data),
        )
        # mock start job response
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            status_code=201,
            text=json.dumps(start_job_response_data),
        )

        file_name = "input.json"
        json_content = """
        {
            "input_key": "input_value"
        }"""

        with runner.isolated_filesystem(temp_dir=temp_dir):
            _create_env_file(mock_env_vars)

            file_path = os.path.join(temp_dir, file_name)
            with open(file_path, "w") as f:
                f.write(json_content)
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            result = runner.invoke(cli, ["invoke", entrypoint, "{}"])
            assert result.exit_code == 0
            assert "Starting job ..." in result.output
            assert "Job started successfully!" in result.output
            assert (
                f"{base_url}/orchestrator_/jobs(sidepanel:sidepanel/jobs/{job_key}/details)?fid={my_workspace_folder_id}"
                in result.output
            )

    def test_invoke_personal_workspace_info_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        entrypoint: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ):
        base_url = mock_env_vars.get("UIPATH_URL")
        # mock start job response
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended?$expand=PersonalWorkspace",
            status_code=204,
        )

        file_name = "input.json"
        json_content = """
        {
            "input_key": "input_value"
        }"""

        with runner.isolated_filesystem(temp_dir=temp_dir):
            _create_env_file(mock_env_vars)

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
                result = runner.invoke(cli, ["invoke", entrypoint, "{}"])
                assert result.exit_code == 1
                assert (
                    "Failed to fetch user info. Please try reauthenticating."
                    in result.output
                )
