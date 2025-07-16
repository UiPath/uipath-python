# type: ignore
import json
import os
import re
from typing import Any, Dict

from click.testing import CliRunner
from httpx import Request
from pytest_httpx import HTTPXMock
from utils.project_details import ProjectDetails
from utils.uipath_json import UiPathJson

from tests.cli.utils.common import configure_env_vars
from uipath._cli.cli_push import push


def extract_agent_json_file_from_request(request: Request) -> dict[Any, str]:
    boundary = re.search(rb"--([a-f0-9]+)", request.content).group(1).decode()
    parts = request.content.split(f"--{boundary}".encode())

    # Locate the agent.json file
    agent_json_part = None
    for part in parts:
        if (
            b'Content-Disposition: form-data; name="file"; filename="agent.json"'
            in part
        ):
            agent_json_part = part
            break

    assert agent_json_part is not None, (
        "agent.json part not found in the multipart/form-data payload."
    )

    # Extract the agent.json content
    agent_json_content = (
        agent_json_part.split(b"\r\n\r\n", 1)[1].split(b"\r\n--")[0].decode()
    )

    # Parse the agent.json payload
    agent_json_data = json.loads(agent_json_content)

    return agent_json_data


class TestPush:
    """Test push command."""

    def test_push_without_uipath_json(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test push when uipath.json is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = "123"
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            result = runner.invoke(push, ["./"])
            assert result.exit_code == 1
            assert (
                "uipath.json not found. Please run `uipath init` in the project directory."
                in result.output
            )

    def test_push_without_project_id(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test push when UIPATH_PROJECT_ID is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            configure_env_vars(mock_env_vars)
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(push, ["./"])
            assert result.exit_code == 1
            assert "UIPATH_PROJECT_ID environment variable not found." in result.output

    def test_successful_push(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful project push with various file operations."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure response
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [
                {
                    "id": "414af585-7e88-4774-ad94-cf6bd48f6c2d",
                    "name": "source_code",
                    "files": [
                        {
                            "id": "123",
                            "name": "main.py",
                            "isMain": True,
                            "fileType": "1",
                            "isEntryPoint": True,
                            "ignoredFromPublish": False,
                        },
                        {
                            "id": "456",
                            "name": "pyproject.toml",
                            "isMain": False,
                            "fileType": "1",
                            "isEntryPoint": False,
                            "ignoredFromPublish": False,
                        },
                        {
                            "id": "789",
                            "name": "uipath.json",
                            "isMain": False,
                            "fileType": "1",
                            "isEntryPoint": False,
                            "ignoredFromPublish": False,
                        },
                    ],
                }
            ],
            "files": [
                {
                    "id": "246",
                    "name": "agent.json",
                    "isMain": False,
                    "fileType": "1",
                    "isEntryPoint": False,
                    "ignoredFromPublish": False,
                },
            ],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        # Mock agent.json download
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/246",
            status_code=200,
            json={"metadata": {"codeVersion": "0.1.0"}},
        )

        # Mock file upload responses
        # For main.py
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/123",
            status_code=200,
        )

        # For pyproject.toml
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            status_code=200,
        )

        # For uipath.json
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            status_code=200,
        )

        # For uv.lock
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # For agent.json
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/246",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write('version = 1 \n requires-python = ">=3.11"')

            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push
            result = runner.invoke(push, ["./"])
            assert result.exit_code == 0
            assert "Updated main.py" in result.output
            assert "Updated pyproject.toml" in result.output
            assert "Updated uipath.json" in result.output
            assert "Uploaded uv.lock" in result.output

            # check incremented code version
            agent_upload_request = None
            for request in httpx_mock.get_requests(
                method="PUT",
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/246",
            ):
                agent_upload_request = request
                break

            agent_json_content = extract_agent_json_file_from_request(
                agent_upload_request
            )

            # Validate `metadata["codeVersion"]`
            expected_code_version = "0.1.1"
            actual_code_version = agent_json_content.get("metadata", {}).get(
                "codeVersion"
            )
            assert actual_code_version == expected_code_version, (
                f"Unexpected codeVersion in metadata. Expected: {expected_code_version}, Got: {actual_code_version}"
            )

    def test_successful_push_new_project(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful project push with various file operations."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure response
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [],
            "folderType": "0",
        }
        # Create source_code folder
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Folder",
            status_code=200,
        )

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        # Mock file upload responses
        # For main.py
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # For pyproject.toml
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # For uipath.json
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # For uv.lock
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # For agent.json
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write('version = 1 \n requires-python = ">=3.11"')

            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push
            result = runner.invoke(push, ["./"])
            print(result.output)
            assert result.exit_code == 0
            assert "Uploaded main.py" in result.output
            assert "Uploaded pyproject.toml" in result.output
            assert "Uploaded uipath.json" in result.output
            assert "Uploaded uv.lock" in result.output

            # check expected agent.json fields
            agent_upload_request = None
            for request in httpx_mock.get_requests(
                method="POST",
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            ):
                if (
                    b'Content-Disposition: form-data; name="file"; filename="agent.json"'
                    in request.content
                ):
                    agent_upload_request = request
                    break

            agent_json_content = extract_agent_json_file_from_request(
                agent_upload_request
            )

            expected_code_version = "1.0.0"
            actual_code_version = agent_json_content.get("metadata", {}).get(
                "codeVersion"
            )
            assert actual_code_version == expected_code_version, (
                f"Unexpected codeVersion in metadata. Expected: {expected_code_version}, Got: {actual_code_version}"
            )
            assert "targetRuntime" in agent_json_content["metadata"]
            assert agent_json_content["metadata"]["targetRuntime"] == "python"
            assert "entryPoints" in agent_json_content
            assert len(agent_json_content["entryPoints"]) == 2
            assert (
                agent_json_content["entryPoints"][0]["input"]["type"]
                == uipath_json.entry_points[0].input.type
            )
            assert (
                "agent_1_output"
                in agent_json_content["entryPoints"][0]["output"]["properties"]
            )

    def test_push_with_api_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test push when API request fails."""
        base_url = "https://cloud.uipath.com/organization"  # Strip tenant part
        project_id = "test-project-id"

        # Mock API error response
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            status_code=401,
            json={"message": "Unauthorized"},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("uv.lock", "w") as f:
                f.write("")

            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(push, ["./"])
            assert result.exit_code == 1
            assert "Failed to get project structure" in result.output

    def test_push_with_nolock_flag(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test push command with --nolock flag."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure response
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [
                {
                    "id": "123",
                    "name": "source_code",
                    "files": [
                        {
                            "id": "123",
                            "name": "main.py",
                            "isMain": True,
                            "fileType": "1",
                            "isEntryPoint": True,
                            "ignoredFromPublish": False,
                        },
                        {
                            "id": "789",
                            "name": "uipath.json",
                            "isMain": False,
                            "fileType": "1",
                            "isEntryPoint": False,
                            "ignoredFromPublish": False,
                        },
                    ],
                }
            ],
            "files": [],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        # Mock file upload responses
        # For main.py
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/123",
            status_code=200,
        )

        # For pyproject.toml
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # For agent.json
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # For uipath.json
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                f.write(uipath_json.to_json())

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write("")
            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push with --nolock flag
            result = runner.invoke(push, ["./", "--nolock"])
            assert result.exit_code == 0
            assert "Updated main.py" in result.output
            assert "Uploaded pyproject.toml" in result.output
            assert "Updated uipath.json" in result.output
            assert "Uploaded agent.json" not in result.output
            assert "uv.lock" not in result.output
