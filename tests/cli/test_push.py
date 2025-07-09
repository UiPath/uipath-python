# type: ignore
import json
import os
from datetime import datetime, timezone
from typing import Dict

from click.testing import CliRunner
from pytest_httpx import HTTPXMock
from utils.project_details import ProjectDetails
from utils.uipath_json import UiPathJson

from uipath._cli._utils._constants import (
    AGENT_INITIAL_CODE_VERSION,
    AGENT_STORAGE_VERSION,
    AGENT_TARGET_RUNTIME,
    AGENT_VERSION,
)
from uipath._cli.cli_push import push


class TestPush:
    """Test push command."""

    def test_push_without_uipath_json(
        self, runner: CliRunner, temp_dir: str, project_details: ProjectDetails
    ) -> None:
        """Test push when uipath.json is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
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
    ) -> None:
        """Test push when UIPATH_PROJECT_ID is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
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
            "folders": [],
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

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                json_content = {
                    "projectId": project_id,
                    "entryPoints": [{"filePath": "main.py", "type": "workflow"}],
                }
                json.dump(json_content, f)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write("")

            # Set environment variables
            os.environ.update(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push
            result = runner.invoke(push, ["./"])

            assert result.exit_code == 0
            assert "Updated main.py" in result.output
            assert "Updated pyproject.toml" in result.output
            assert "Updated uipath.json" in result.output
            assert "Uploaded uv.lock" in result.output

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
            os.environ.update(mock_env_vars)
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
            "folders": [],
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

        # For uipath.json
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                json_content = {
                    "projectId": project_id,
                    "entryPoints": [{"filePath": "main.py", "type": "workflow"}],
                }
                json.dump(json_content, f)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write("")
            # Set environment variables
            os.environ.update(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push with --nolock flag
            result = runner.invoke(push, ["./", "--nolock"])
            print(result.output)
            assert result.exit_code == 0
            assert "Updated main.py" in result.output
            assert "Uploaded pyproject.toml" in result.output
            assert "Updated uipath.json" in result.output
            assert "uv.lock" not in result.output

    def test_agent_json_handling(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test agent.json creation, update, and version incrementing.

        This test verifies:
        1. Initial agent.json creation when it doesn't exist
        2. Updating existing agent.json with version increment
        3. Proper metadata handling
        4. Correct entrypoint mapping from uipath.json
        5. File persistence (not being deleted)
        """
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock initial project structure without agent.json
        initial_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "main.py",
                    "isMain": True,
                    "fileType": "1",
                    "isEntryPoint": True,
                    "ignoredFromPublish": False,
                }
            ],
            "folderType": "0",
        }

        # Mock project structure after agent.json is created
        updated_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
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
                    "name": "agent.json",
                    "isMain": False,
                    "fileType": "1",
                    "isEntryPoint": False,
                    "ignoredFromPublish": False,
                },
            ],
            "folderType": "0",
        }

        # Mock the initial project structure response
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=initial_structure,
        )

        # Mock agent.json creation response
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File",
            status_code=200,
        )

        # Mock the second project structure response (after agent.json is created)
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=updated_structure,
        )

        # Mock existing agent.json content response
        existing_agent_json = {
            "version": AGENT_VERSION,
            "metadata": {
                "storageVersion": AGENT_STORAGE_VERSION,
                "targetRuntime": AGENT_TARGET_RUNTIME,
                "isConversational": False,
                "codeVersion": "1.0.0",
                "author": "test@example.com",
                "pushdate": datetime.now(timezone.utc).isoformat(),
            },
            "entrypoints": [
                {
                    "input": {"type": "object", "properties": {}},
                    "output": {"type": "object", "properties": {}},
                }
            ],
            "bindings": {"version": "2.0", "resources": []},
        }

        # Mock agent.json content response
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            json=existing_agent_json,
        )

        # Mock agent.json update response
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            status_code=200,
        )

        # Mock other file responses
        httpx_mock.add_response(
            method="PUT",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/123",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            with open("uipath.json", "w") as f:
                json_content = {
                    "projectId": project_id,
                    "entryPoints": [
                        {
                            "filePath": "main.py",
                            "type": "workflow",
                            "input": {
                                "type": "object",
                                "properties": {"message": {"type": "string"}},
                            },
                            "output": {
                                "type": "object",
                                "properties": {"result": {"type": "string"}},
                            },
                        }
                    ],
                }
                json.dump(json_content, f)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            # Set environment variables
            os.environ.update(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push
            result = runner.invoke(push, ["./"])

            assert result.exit_code == 0
            assert "Updated agent.json" in result.output
            assert "Updated main.py" in result.output
            assert "Deleted remote file agent.json" not in result.output

            # Verify all expected requests were made
            requests = httpx_mock.get_requests()
            urls = [req.url.path for req in requests]

            # Check for structure requests
            assert any("FileOperations/Structure" in url for url in urls)

            # Check for agent.json operations
            assert any("FileOperations/File/456" in url for url in urls)

            # Verify no delete operations for agent.json
            assert not any(f"FileOperations/Delete/456" in url for url in urls)
