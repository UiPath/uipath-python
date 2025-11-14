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
from uipath._cli import cli


def extract_agent_json_from_modified_resources(
    request: Request, *, agent_file_id: str | None = None
) -> dict[str, Any]:
    """Extract agent.json content from ModifiedResources in StructuralMigration payload."""
    match = re.search(
        rb"boundary=([-._0-9A-Za-z]+)", request.headers.get("Content-Type", "").encode()
    )
    if match is None:
        # Fallback to body sniffing like older helper
        match = re.search(rb"--([-._0-9A-Za-z]+)", request.content)
    assert match is not None, "Could not detect multipart boundary"
    boundary = match.group(1)
    parts = request.content.split(b"--" + boundary)

    # Require agent_file_id and search only ModifiedResources
    assert agent_file_id is not None, (
        "agent_file_id is required to extract agent.json from ModifiedResources"
    )
    target_index: str | None = None
    for part in parts:
        if (
            b"Content-Disposition: form-data;" in part
            and b"ModifiedResources[" in part
            and b"].Id" in part
        ):
            body = part.split(b"\r\n\r\n", 1)
            if len(body) == 2:
                value = body[1].strip().strip(b"\r\n")
                if value.decode(errors="ignore") == agent_file_id:
                    m = re.search(rb"ModifiedResources\[(\d+)\]\.Id", part)
                    if m:
                        target_index = m.group(1).decode()
                        break

    if target_index is not None:
        for part in parts:
            if (
                b"Content-Disposition: form-data;" in part
                and f"ModifiedResources[{target_index}].Content".encode() in part
            ):
                content_bytes = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0]
                return json.loads(content_bytes.decode())

    raise AssertionError(
        "agent.json content not found in ModifiedResources of StructuralMigration payload"
    )


def extract_agent_json_from_added_resources(request: Request) -> dict[str, Any]:
    """Extract agent.json content from AddedResources in StructuralMigration payload."""
    match = re.search(
        rb"boundary=([-._0-9A-Za-z]+)", request.headers.get("Content-Type", "").encode()
    )
    if match is None:
        match = re.search(rb"--([-._0-9A-Za-z]+)", request.content)
    assert match is not None, "Could not detect multipart boundary"
    boundary = match.group(1)
    parts = request.content.split(b"--" + boundary)

    for part in parts:
        if (
            b"Content-Disposition: form-data;" in part
            and b"AddedResources[" in part
            and b"].Content" in part
            and b'filename="agent.json"' in part
        ):
            content_bytes = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0]
            return json.loads(content_bytes.decode())

    raise AssertionError(
        "agent.json content not found in AddedResources of StructuralMigration payload"
    )


class TestPush:
    """Test push command."""

    def _create_required_files(self, exclude: list[str] | None = None):
        required_files = ["uipath.json", "bindings.json", "entry-points.json"]
        for file in required_files:
            if exclude and file in exclude:
                continue
            with open(file, "w") as file:
                file.write("{}")

    def test_push_without_uipath_json(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test push when uipath.json is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = "123"
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 1
            assert (
                "uipath.json not found. Please run `uipath init` in the project directory."
                in result.output
            )

    def test_push_without_required_files_shows_specific_missing(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test push shows specific missing files when uipath.json and .uipath are missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = "123"

            self._create_required_files(exclude=["bindings.json", "entry-points.json"])

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 1
            # Should show exactly which file is missing
            assert (
                "Missing required files: 'bindings.json', 'entry-points.json'"
                in result.output
            )
            assert "Please run 'uipath init'" in result.output

    def test_push_with_only_enty_points_json_missing(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test push when .uipath directory exists but uipath.json is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["entry-points.json"])

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = "123"

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 1
            # Should show exactly which file is missing
            assert "Missing required files: 'entry-points.json'" in result.output
            assert "Please run 'uipath init'" in result.output

    def test_push_without_project_id(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test push when UIPATH_PROJECT_ID is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()
            configure_env_vars(mock_env_vars)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 1
            assert "UIPATH_PROJECT_ID environment variable not found." in result.output

    def test_successful_push(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
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
                {
                    "id": "246",
                    "name": "agent.json",
                    "isMain": False,
                    "fileType": "1",
                    "isEntryPoint": False,
                    "ignoredFromPublish": False,
                },
                {
                    "id": "898",
                    "name": "entry-points.json",
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

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        # Mock file downloads for conflict detection
        # Mock main.py download - return different content to trigger update
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/123",
            status_code=200,
            text="print('Old version')",
        )

        # Mock pyproject.toml download - return different content to trigger update
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            status_code=200,
            text="[project]\nname = 'old-version'\n",
        )

        # Mock uipath.json download - return different content to trigger update
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            status_code=200,
            text='{"version": "old"}',
        )

        # Mock agent.json download
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/246",
            status_code=200,
            json={"metadata": {"codeVersion": "0.1.0"}},
        )

        # Mock entry-points.json download
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/898",
            status_code=200,
            json={"entryPoints": {}},
        )

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        # Mock empty folder cleanup - get structure again after migration
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            self._create_required_files()

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
            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0
            assert "Updating 'main.py'" in result.output
            assert "Updating 'pyproject.toml'" in result.output
            assert "Updating 'uipath.json'" in result.output
            assert "Uploading 'uv.lock'" in result.output
            assert "Updating 'agent.json'" in result.output
            assert "Updating 'entry-points.json'" in result.output

            # check incremented code version via StructuralMigration payload
            structural_migration_request = httpx_mock.get_request(
                method="POST",
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            )
            assert structural_migration_request is not None
            agent_json_content = extract_agent_json_from_modified_resources(
                structural_migration_request, agent_file_id="246"
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
        uipath_json_legacy: UiPathJson,
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

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        # Mock empty folder cleanup - get structure again after migration
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            self._create_required_files(exclude=["entry-points.json"])

            with open("entry-points.json", "w") as f:
                json.dump(
                    {
                        "entryPoints": json.loads(uipath_json_legacy.to_json()).get(
                            "entryPoints"
                        )
                    },
                    f,
                )

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
            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0
            assert "Uploading 'main.py'" in result.output
            assert "Uploading 'pyproject.toml'" in result.output
            assert "Uploading 'uipath.json'" in result.output
            assert "Uploading 'uv.lock'" in result.output
            assert "Uploading 'agent.json'" in result.output
            assert "Uploading 'entry-points.json'" in result.output

            # check expected agent.json fields
            structural_migration_request = httpx_mock.get_request(
                method="POST",
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            )
            assert structural_migration_request is not None
            agent_json_content = extract_agent_json_from_added_resources(
                structural_migration_request
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

    def test_push_with_api_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
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
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("uv.lock", "w") as f:
                f.write("")

            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 1
            assert "Failed to push UiPath project" in result.output
            assert "Status Code: 401" in result.output

    def test_push_with_nolock_flag(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
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

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        # Mock file downloads for conflict detection
        # Mock main.py download - return different content to trigger update
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/123",
            status_code=200,
            text="print('Old version')",
        )

        # Mock uipath.json download - return different content to trigger update
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            status_code=200,
            text='{"version": "old"}',
        )

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        # Mock empty folder cleanup - get structure again after migration
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create necessary files
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write("")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push with --nolock flag
            result = runner.invoke(cli, ["push", "./", "--nolock"])
            assert result.exit_code == 0
            assert "Updating 'main.py'" in result.output
            assert "Uploading 'pyproject.toml'" in result.output
            assert "Updating 'uipath.json'" in result.output
            assert "uv.lock" not in result.output

    def _mock_lock_retrieval(
        self, httpx_mock: HTTPXMock, base_url: str, project_id: str, times: int
    ):
        for _ in range(times):
            httpx_mock.add_response(
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/Lock",
                json={
                    "projectLockKey": "test-lock-key",
                    "solutionLockKey": "test-solution-lock-key",
                },
            )

    def test_push_files_excluded(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that files mentioned in filesExcluded are excluded from push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Set up exclusions - exclude a JSON file that would normally be included
        uipath_json_legacy.settings.files_excluded = ["config.json"]

        # Mock the project structure response (empty project)
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        # Mock empty folder cleanup
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])

            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create files - config.json should be excluded, other.json should be included
            with open("config.json", "w") as f:
                f.write('{"should": "be excluded"}')
            with open("other.json", "w") as f:
                f.write('{"should": "be included"}')
            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0

            # Verify that excluded file was not mentioned in output
            assert "config.json" not in result.output
            # Verify that other files were uploaded
            assert "Uploading 'other.json'" in result.output
            assert "Uploading 'main.py'" in result.output

    def test_push_files_excluded_takes_precedence_over_included(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that filesExcluded takes precedence over filesIncluded in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Set up both inclusion and exclusion for the same file
        uipath_json_legacy.settings.files_included = ["conflicting.txt"]
        uipath_json_legacy.settings.files_excluded = ["conflicting.txt"]

        # Mock the project structure response (empty project)
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        # Mock empty folder cleanup
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])

            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create the conflicting file
            with open("conflicting.txt", "w") as f:
                f.write("This file should be excluded despite being in filesIncluded")
            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0

            # File should be excluded (exclusion takes precedence)
            assert "conflicting.txt" not in result.output
            # Verify other files were uploaded
            assert "Uploading 'main.py'" in result.output

    def test_push_filename_vs_path_exclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that filename exclusion only affects root directory, path exclusion affects specific paths in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Exclude root config.json and specific path subdir2/settings.json
        uipath_json_legacy.settings.files_excluded = [
            "config.json",
            "subdir2/settings.json",
        ]

        # Mock empty project structure
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])

            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create directories
            os.mkdir("subdir1")
            os.mkdir("subdir2")

            # Create files with same names in different locations
            with open("config.json", "w") as f:  # Root - should be excluded
                f.write('{"root": "config"}')
            with open("subdir1/config.json", "w") as f:  # Subdir - should be included
                f.write('{"subdir1": "config"}')
            with open("subdir2/config.json", "w") as f:  # Subdir - should be included
                f.write('{"subdir2": "config"}')

            with open("settings.json", "w") as f:  # Root - should be included
                f.write('{"root": "settings"}')
            with open("subdir1/settings.json", "w") as f:  # Subdir - should be included
                f.write('{"subdir1": "settings"}')
            with open(
                "subdir2/settings.json", "w"
            ) as f:  # Specific path - should be excluded
                f.write('{"subdir2": "settings"}')

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0

            # Filename exclusion should only affect root directory
            # Since we exclude root config.json, it shouldn't appear in output
            # But subdirectory config.json files should still be uploaded

            # Path exclusion should only affect specific path
            # settings.json in root and subdir1 should be uploaded
            # but subdir2/settings.json should be excluded

            assert (
                "settings.json" in result.output
            )  # At least some settings.json should be present
            assert "Uploading 'main.py'" in result.output

    def test_push_filename_vs_path_inclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that filename inclusion only affects root directory, path inclusion affects specific paths in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Include root data.txt and specific path subdir1/config.txt
        uipath_json_legacy.settings.files_included = ["data.txt", "subdir1/config.txt"]

        # Mock empty project structure
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])

            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create directories
            os.mkdir("subdir1")
            os.mkdir("subdir2")

            # Create .txt files (not included by default extension)
            with open("data.txt", "w") as f:  # Root - should be included by filename
                f.write("root data")
            with open("subdir1/data.txt", "w") as f:  # Subdir - should NOT be included
                f.write("subdir1 data")
            with open(
                "subdir2/data.txt", "w"
            ) as f:  # Different subdir - should NOT be included
                f.write("subdir2 data")

            with open("config.txt", "w") as f:  # Root - should NOT be included
                f.write("root config")
            with open(
                "subdir1/config.txt", "w"
            ) as f:  # Specific path - should be included
                f.write("subdir1 config")
            with open(
                "subdir2/config.txt", "w"
            ) as f:  # Different path - should NOT be included
                f.write("subdir2 config")

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0

            # Filename inclusion should only affect root directory
            # data.txt in root should be included, but not in subdirectories

            # Path inclusion should only affect specific path
            # subdir1/config.txt should be included, but not root or subdir2

            assert (
                "data.txt" in result.output or "config.txt" in result.output
            )  # At least one should be present
            assert "Uploading 'main.py'" in result.output

    def test_push_directory_name_vs_path_exclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that directory exclusion by name only affects root level, by path affects specific paths in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Exclude root-level "temp" directory and specific path "tests/old"
        uipath_json_legacy.settings.directories_excluded = ["temp", "tests/old"]

        # Mock empty project structure
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])

            with open("uipath.json", "w") as f:
                f.write(uipath_json_legacy.to_json())
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            # Create directory structure
            os.makedirs("temp")  # Root level - should be excluded
            os.makedirs("src/temp")  # Nested - should be included
            os.makedirs("tests/old")  # Specific path - should be excluded
            os.makedirs("tests/new")  # Different path - should be included
            os.makedirs("old")  # Root level - should be included

            # Create JSON files in each directory (included by default)
            with open("temp/config.json", "w") as f:
                f.write('{"location": "root temp"}')
            with open("src/temp/config.json", "w") as f:
                f.write('{"location": "src temp"}')
            with open("tests/old/config.json", "w") as f:
                f.write('{"location": "tests old"}')
            with open("tests/new/config.json", "w") as f:
                f.write('{"location": "tests new"}')
            with open("old/config.json", "w") as f:
                f.write('{"location": "root old"}')

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0

            # Directory name exclusion should only affect root level
            # temp/ directory should be excluded, so temp/config.json shouldn't appear
            # but src/temp/config.json should be uploaded

            # Directory path exclusion should only affect specific path
            # tests/old/ should be excluded, but tests/new/ and old/ should be uploaded

            # Since we exclude root temp/, its files shouldn't appear
            # Since we exclude tests/old/, its files shouldn't appear
            # Other directories should have their files uploaded

            assert (
                "config.json" in result.output
            )  # Some config.json should be present from allowed directories
            assert "Uploading 'main.py'" in result.output

    def test_push_detects_source_file_conflicts(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
        monkeypatch: Any,
    ) -> None:
        """Test that push detects conflicts when remote files differ from local files."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure with existing files
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "456",
                    "name": "main.py",
                    "isMain": True,
                    "fileType": "1",
                    "isEntryPoint": True,
                    "ignoredFromPublish": False,
                },
            ],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        # Mock file download - return different content to detect conflict
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            status_code=200,
            text="print('Remote version')",
        )

        # Mock user confirmation - user confirms the overwrite
        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("main.py", "w") as f:
                f.write("print('Local version')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0
            # Should detect conflict and update after user confirmation
            assert "Updating 'main.py'" in result.output

    def test_push_skips_file_when_user_rejects(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
        monkeypatch: Any,
    ) -> None:
        """Test that push skips files when user rejects overwrite."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure with existing files
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "456",
                    "name": "main.py",
                    "isMain": True,
                    "fileType": "1",
                    "isEntryPoint": True,
                    "ignoredFromPublish": False,
                },
            ],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        # Mock file download - return different content to detect conflict
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            status_code=200,
            text="print('Remote version')",
        )

        # Mock user confirmation - user rejects the overwrite
        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("main.py", "w") as f:
                f.write("print('Local version')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0
            # Should skip the file after user rejection
            assert "Skipped 'main.py'" in result.output
            assert "Updating 'main.py'" not in result.output

    def test_push_updates_file_when_user_confirms(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
        monkeypatch: Any,
    ) -> None:
        """Test that push updates file when user confirms overwrite."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure with existing files
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "456",
                    "name": "main.py",
                    "isMain": True,
                    "fileType": "1",
                    "isEntryPoint": True,
                    "ignoredFromPublish": False,
                },
                {
                    "id": "789",
                    "name": "helper.py",
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

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        # Mock file downloads - return different content to detect conflicts
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            status_code=200,
            text="print('Old main')",
        )

        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            status_code=200,
            text="def old_helper(): pass",
        )

        # Mock user confirmation - user confirms all overwrites
        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("main.py", "w") as f:
                f.write("print('New main')")
            with open("helper.py", "w") as f:
                f.write("def new_helper(): pass")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0
            # Both files should be updated after user confirmation
            assert "Updating 'main.py'" in result.output
            assert "Updating 'helper.py'" in result.output

    def test_push_shows_up_to_date_for_unchanged_files(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that push shows 'up to date' message for files that haven't changed."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        local_main_content = "print('Same version')"
        local_helper_content = "def helper(): pass"

        # Mock the project structure with existing files
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "456",
                    "name": "main.py",
                    "isMain": True,
                    "fileType": "1",
                    "isEntryPoint": True,
                    "ignoredFromPublish": False,
                },
                {
                    "id": "789",
                    "name": "helper.py",
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

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        # Mock file downloads - return same content as local files
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            status_code=200,
            text=local_main_content,
        )

        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            status_code=200,
            text=local_helper_content,
        )

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("main.py", "w") as f:
                f.write(local_main_content)
            with open("helper.py", "w") as f:
                f.write(local_helper_content)

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0
            # Files should show as up to date since content matches
            assert "File 'main.py' is up to date" in result.output
            assert "File 'helper.py' is up to date" in result.output
            # Should not show updating messages
            assert "Updating 'main.py'" not in result.output
            assert "Updating 'helper.py'" not in result.output

    def test_push_preserves_remote_evals_when_no_local_evals(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that remote evaluations files are not deleted when no local evals folder exists."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure with existing evaluations folder and files
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [
                {
                    "id": "evaluations-folder-id",
                    "name": "evaluations",
                    "folders": [
                        {
                            "id": "evaluators-folder-id",
                            "name": "evaluators",
                            "files": [
                                {
                                    "id": "evaluator-file-1",
                                    "name": "evaluator-1.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                },
                            ],
                            "folders": [],
                        },
                        {
                            "id": "eval-sets-folder-id",
                            "name": "eval-sets",
                            "files": [
                                {
                                    "id": "eval-set-file-1",
                                    "name": "eval-set-1.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                },
                            ],
                            "folders": [],
                        },
                    ],
                    "files": [],
                },
            ],
            "files": [
                {
                    "id": "main-456",
                    "name": "main.py",
                    "isMain": True,
                    "fileType": "1",
                    "isEntryPoint": True,
                    "ignoredFromPublish": False,
                },
            ],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        self._mock_lock_retrieval(httpx_mock, base_url, project_id, times=1)

        # Mock file download for main.py - return same content to avoid conflict
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/main-456",
            status_code=200,
            text="print('Hello World')",
        )

        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            status_code=200,
            json={"success": True},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            # Importantly: Do NOT create any evals folder or files locally

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./"])
            assert result.exit_code == 0

            # Verify that no deletion messages appear for evaluations files
            assert (
                "Deleting evaluations/evaluators/evaluator-1.json" not in result.output
            )
            assert "Deleting evaluations/eval-sets/eval-set-1.json" not in result.output

            # Get the StructuralMigration request to verify no deletions were sent
            structural_migration_request = httpx_mock.get_request(
                method="POST",
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            )
            assert structural_migration_request is not None

            # Parse the multipart form data to check deleted_resources
            # The deleted_resources should not include the evaluations files
            content = structural_migration_request.content

            # Check that the deleted resource IDs are not present in the request
            assert b"evaluator-file-1" not in content
            assert b"eval-set-file-1" not in content
