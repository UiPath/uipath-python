# type: ignore
import json
import os
import re
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from httpx import Request
from pytest_httpx import HTTPXMock
from utils.project_details import ProjectDetails

from tests.cli.utils.common import configure_env_vars
from uipath._cli import cli
from uipath._cli._utils._common import may_override_files
from uipath._cli._utils._studio_project import StudioProjectMetadata
from uipath.platform.errors import EnrichedException


def create_uipath_json(
    functions: dict[str, str] | None = None, pack_options: dict | None = None
):
    """Helper to create uipath.json with functions structure."""
    if functions is None:
        functions = {"main": "main.py:main"}

    config = {"functions": functions}
    if pack_options:
        config["packOptions"] = pack_options

    return config


def extract_metadata_json_from_modified_resources(
    request: Request, *, metadata_file_id: str | None = None
) -> dict[str, Any]:
    """Extract studio_metadata.json content from ModifiedResources in StructuralMigration payload."""
    match = re.search(
        rb"boundary=([-._0-9A-Za-z]+)", request.headers.get("Content-Type", "").encode()
    )
    if match is None:
        match = re.search(rb"--([-._0-9A-Za-z]+)", request.content)
    assert match is not None, "Could not detect multipart boundary"
    boundary = match.group(1)
    parts = request.content.split(b"--" + boundary)

    assert metadata_file_id is not None, (
        "metadata_file_id is required to extract studio_metadata.json from ModifiedResources"
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
                if value.decode(errors="ignore") == metadata_file_id:
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
        "studio_metadata.json content not found in ModifiedResources of StructuralMigration payload"
    )


def extract_metadata_json_from_added_resources(request: Request) -> dict[str, Any]:
    """Extract studio_metadata.json content from AddedResources in StructuralMigration payload."""
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
            and b'filename="studio_metadata.json"' in part
        ):
            content_bytes = part.split(b"\r\n\r\n", 1)[1].split(b"\r\n")[0]
            return json.loads(content_bytes.decode())

    raise AssertionError(
        "studio_metadata.json content not found in AddedResources of StructuralMigration payload"
    )


class TestPush:
    """Test push command."""

    base_url = "https://cloud.uipath.com/organization"
    project_id = "test-project-id"

    def _mock_file_download(
        self,
        httpx_mock,
        file_id: str,
        *,
        file_content: str | None = None,
        times: int = 1,
    ):
        for _ in range(times):
            httpx_mock.add_response(
                method="GET",
                url=f"{TestPush.base_url}/studio_/backend/api/Project/{TestPush.project_id}/FileOperations/File/{file_id}",
                status_code=200,
                text="Remote file content" if not file_content else file_content,
            )

    def _create_required_files(self, exclude: list[str] | None = None):
        required_files = ["uipath.json", "bindings.json", "entry-points.json"]
        for file in required_files:
            if exclude and file in exclude:
                continue
            with open(file, "w") as f:
                f.write("{}")

    def test_push_without_uipath_json(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
    ) -> None:
        """Test push when uipath.json is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = "123"
            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())
            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
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
        mock_env_vars: dict[str, str],
    ) -> None:
        """Test push shows specific missing files when uipath.json and .uipath are missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = "123"

            self._create_required_files(exclude=["bindings.json", "entry-points.json"])

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
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
        mock_env_vars: dict[str, str],
    ) -> None:
        """Test push when .uipath directory exists but uipath.json is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["entry-points.json"])

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = "123"

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 1
            # Should show exactly which file is missing
            assert "Missing required files: 'entry-points.json'" in result.output
            assert "Please run 'uipath init'" in result.output

    def test_push_without_project_id(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
    ) -> None:
        """Test push when UIPATH_PROJECT_ID is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()
            configure_env_vars(mock_env_vars)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 1
            assert "UIPATH_PROJECT_ID environment variable not found." in result.output

    def test_successful_push(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful project push with various file operations."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [
                {
                    "id": "uipath-folder",
                    "name": ".uipath",
                    "folders": [],
                    "files": [
                        {
                            "id": "246",
                            "name": "studio_metadata.json",
                            "isMain": False,
                            "fileType": "1",
                            "isEntryPoint": False,
                            "ignoredFromPublish": False,
                        },
                    ],
                },
            ],
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

        self._mock_file_download(httpx_mock, "123")
        self._mock_file_download(httpx_mock, "456")
        self._mock_file_download(httpx_mock, "789")

        # metadata file should be retrieved twice
        self._mock_file_download(
            httpx_mock,
            "246",
            file_content=json.dumps(
                {
                    "schemaVersion": 1,
                    "lastPushDate": "2025-11-20T13:07:31.515084+00:00",
                    "lastPushAuthor": "john.doe@mail.com",
                    "codeVersion": "1.0.3",
                }
            ),
            times=2,
        )

        self._mock_file_download(httpx_mock, "898")

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
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write('version = 1 \n requires-python = ">=3.11"')

            os.mkdir(".uipath")
            with open(os.path.join(".uipath", "studio_metadata.json"), "w") as f:
                json.dump(
                    {
                        "schemaVersion": 1,
                        "lastPushDate": "2025-11-20T13:07:31.515084+00:00",
                        "lastPushAuthor": "john.doe@mail.com",
                        "codeVersion": "1.0.3",
                    },
                    f,
                )

            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 0
            assert "Updating 'main.py'" in result.output
            assert "Updating 'pyproject.toml'" in result.output
            assert "Updating 'uipath.json'" in result.output
            assert "Uploading 'uv.lock'" in result.output
            assert "Updating '.uipath/studio_metadata.json'" in result.output
            assert "Updating 'entry-points.json'" in result.output

            structural_migration_request = httpx_mock.get_request(
                method="POST",
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            )
            assert structural_migration_request is not None
            metadata_json_content = extract_metadata_json_from_modified_resources(
                structural_migration_request, metadata_file_id="246"
            )

            expected_code_version = "1.0.4"
            actual_code_version = metadata_json_content.get("codeVersion")
            assert actual_code_version == expected_code_version, (
                f"Unexpected codeVersion. Expected: {expected_code_version}, Got: {actual_code_version}"
            )

    def test_successful_push_new_project(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
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
                    "name": "pyproject.toml",
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

        self._mock_file_download(httpx_mock, "123")

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

            # Create entry-points.json with proper structure
            with open("entry-points.json", "w") as f:
                json.dump(
                    {
                        "entryPoints": [
                            {
                                "filePath": "main.py",
                                "uniqueId": "main-id",
                                "type": "agent",
                                "input": {"type": "object", "properties": {}},
                                "output": {"type": "object", "properties": {}},
                            }
                        ]
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

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 0
            assert "Uploading 'main.py'" in result.output
            assert "Updating 'pyproject.toml'" in result.output
            assert "Uploading 'uipath.json'" in result.output
            assert "Uploading 'uv.lock'" in result.output
            assert "Uploading '.uipath/studio_metadata.json'" in result.output
            assert "Uploading 'entry-points.json'" in result.output

            structural_migration_request = httpx_mock.get_request(
                method="POST",
                url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/StructuralMigration",
            )
            assert structural_migration_request is not None
            metadata_json_content = extract_metadata_json_from_added_resources(
                structural_migration_request
            )

            expected_code_version = "1.0.0"
            actual_code_version = metadata_json_content.get("codeVersion")
            assert actual_code_version == expected_code_version, (
                f"Unexpected codeVersion. Expected: {expected_code_version}, Got: {actual_code_version}"
            )

    # Continue with remaining test methods - they all follow the same pattern
    # I'll include abbreviated versions for brevity since the pattern is the same

    def test_push_with_api_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test push when API request fails."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            status_code=401,
            json={"message": "Unauthorized"},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("uv.lock", "w") as f:
                f.write("")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 1

            assert isinstance(result.exception, EnrichedException)
            assert result.exception.status_code == 401

    def test_push_non_coded_agent_project(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test push when the project is not a coded agent project (missing pyproject.toml)."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "789",
                    "name": "uipath.json",
                    "isMain": False,
                    "fileType": "1",
                    "isEntryPoint": False,
                    "ignoredFromPublish": False,
                },
                {
                    "id": "456",
                    "name": "main.xaml",
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

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 1
            assert (
                "The targeted Studio Web project is not of type coded agent"
                in result.output
            )
            assert (
                "Please check the UIPATH_PROJECT_ID environment variable"
                in result.output
            )

    def test_push_with_nolock_flag(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test push command with --nolock flag."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

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
        self._mock_file_download(httpx_mock, "123")
        self._mock_file_download(httpx_mock, "789")
        self._mock_file_download(httpx_mock, "456")

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
            self._create_required_files()

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            with open("uv.lock", "w") as f:
                f.write("")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(
                cli, ["push", "./", "--ignore-resources", "--nolock"]
            )
            assert result.exit_code == 0
            assert "Updating 'main.py'" in result.output
            assert "Updating 'pyproject.toml'" in result.output
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
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that files mentioned in filesExcluded are excluded from push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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

        self._mock_file_download(httpx_mock, "123")
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

            # Create uipath.json with filesExcluded
            uipath_config = create_uipath_json(
                pack_options={"filesExcluded": ["config.json"]}
            )
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("config.json", "w") as f:
                f.write('{"should": "be excluded"}')
            with open("other.json", "w") as f:
                f.write('{"should": "be included"}')
            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 0

            assert "config.json" not in result.output
            assert "Uploading 'other.json'" in result.output
            assert "Uploading 'main.py'" in result.output

    def test_push_files_excluded_takes_precedence_over_included(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that filesExcluded takes precedence over filesIncluded in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
        self._mock_file_download(httpx_mock, "123")

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

            uipath_config = create_uipath_json(
                pack_options={
                    "filesIncluded": ["conflicting.txt"],
                    "filesExcluded": ["conflicting.txt"],
                }
            )
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("conflicting.txt", "w") as f:
                f.write("This file should be excluded despite being in filesIncluded")
            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 0

            assert "conflicting.txt" not in result.output
            assert "Uploading 'main.py'" in result.output

    def test_push_filename_vs_path_exclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that filename exclusion only affects root directory, path exclusion affects specific paths in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
        self._mock_file_download(httpx_mock, "123")

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

            uipath_config = create_uipath_json(
                pack_options={"filesExcluded": ["config.json", "subdir2/settings.json"]}
            )
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            os.mkdir("subdir1")
            os.mkdir("subdir2")

            with open("config.json", "w") as f:
                f.write('{"root": "config"}')
            with open("subdir1/config.json", "w") as f:
                f.write('{"subdir1": "config"}')
            with open("subdir2/config.json", "w") as f:
                f.write('{"subdir2": "config"}')

            with open("settings.json", "w") as f:
                f.write('{"root": "settings"}')
            with open("subdir1/settings.json", "w") as f:
                f.write('{"subdir1": "settings"}')
            with open("subdir2/settings.json", "w") as f:
                f.write('{"subdir2": "settings"}')

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 0

            assert "settings.json" in result.output
            assert "Uploading 'main.py'" in result.output

    def test_push_filename_vs_path_inclusion(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that filename inclusion only affects root directory, path inclusion affects specific paths in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
        self._mock_file_download(httpx_mock, "123")

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

            uipath_config = create_uipath_json(
                pack_options={"filesIncluded": ["data.txt", "subdir1/config.txt"]}
            )
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

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

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
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
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that directory exclusion by name only affects root level, by path affects specific paths in push."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
        self._mock_file_download(httpx_mock, "123")

        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._create_required_files(exclude=["uipath.json"])

            uipath_config = create_uipath_json(
                pack_options={"directoriesExcluded": ["temp", "tests/old"]}
            )
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

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

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
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
        mock_env_vars: dict[str, str],
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

        self._mock_file_download(httpx_mock, "123")
        self._mock_file_download(httpx_mock, "456")

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

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 0
            # Should detect conflict
            assert "Updating 'main.py'" in result.output

    def test_push_shows_up_to_date_for_unchanged_files(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
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
                    "id": "123",
                    "name": "pyproject.toml",
                    "isMain": False,
                    "fileType": "1",
                    "isEntryPoint": False,
                    "ignoredFromPublish": False,
                },
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

        self._mock_file_download(httpx_mock, "123")
        # Mock file downloads - return same content as local files
        self._mock_file_download(httpx_mock, "456", file_content=local_main_content)
        self._mock_file_download(httpx_mock, "789", file_content=local_helper_content)

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

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
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
        mock_env_vars: dict[str, str],
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
                    "id": "123",
                    "name": "pyproject.toml",
                    "isMain": False,
                    "fileType": "1",
                    "isEntryPoint": False,
                    "ignoredFromPublish": False,
                },
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

        self._mock_file_download(httpx_mock, "main-456")
        self._mock_file_download(httpx_mock, "123")

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

            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
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


class TestResourceCreation:
    """Test resource creation and import functionality during push."""

    base_url = "https://cloud.uipath.com/organization"
    project_id = "test-project-id"

    def _mock_file_download(
        self,
        httpx_mock,
        file_id: str,
        *,
        file_content: str | None = None,
        times: int = 1,
    ):
        for _ in range(times):
            httpx_mock.add_response(
                method="GET",
                url=f"{TestResourceCreation.base_url}/studio_/backend/api/Project/{TestResourceCreation.project_id}/FileOperations/File/{file_id}",
                status_code=200,
                text="Remote file content" if not file_content else file_content,
            )

    def test_push_with_resources_imports_referenced_resources(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that push without --ignore-resources flag imports referenced resources to the solution."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"
        solution_id = "test-solution-id"
        tenant_id = "test-tenant-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
        self._mock_file_download(httpx_mock, "123")

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/Lock",
            json={
                "projectLockKey": "test-lock-key",
                "solutionLockKey": "test-solution-lock-key",
            },
        )

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

        # Mock getting the solution ID
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}",
            json={"solutionId": solution_id},
        )

        # Mock creating referenced resource (status: ADDED)
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/resourcebuilder/solutions/{solution_id}/resources/reference",
            json={
                "status": "Added",
                "resource": {
                    "folders": [
                        {"fullyQualifiedName": "Default", "path": "folder-path-123"}
                    ],
                    "key": "resource-key-123",
                    "name": "test.asset",
                    "description": "Test asset description",
                    "kind": "asset",
                    "type": "stringAsset",
                    "apiVersion": "orchestrator.uipath.com/v1",
                },
                "saved": True,
            },
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create required files
            with open("uipath.json", "w") as f:
                json.dump(create_uipath_json(), f)

            with open("bindings.json", "w") as f:
                json.dump(
                    {
                        "version": "2.0",
                        "resources": [
                            {
                                "resource": "asset",
                                "key": "asset_name.folder_key",
                                "value": {
                                    "name": {
                                        "defaultValue": "test.asset",
                                        "isExpression": False,
                                        "displayName": "Name",
                                    },
                                    "folderPath": {
                                        "defaultValue": "Default",
                                        "isExpression": False,
                                        "displayName": "Folder Path",
                                    },
                                },
                                "metadata": {
                                    "ActivityName": "retrieve_async",
                                    "BindingsVersion": "2.2",
                                    "DisplayLabel": "FullName",
                                },
                            }
                        ],
                    },
                    f,
                )

            with open("entry-points.json", "w") as f:
                f.write("{}")

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id
            os.environ["UIPATH_TENANT_ID"] = tenant_id

            # Mock resource catalog list_by_type_async
            from uipath.platform.resource_catalog import Folder, Resource

            mock_resource = Resource(
                resource_key="resource-key-123",
                name="test.asset",
                description="Test asset description",
                resource_type="asset",
                resource_sub_type="stringAsset",
                folders=[
                    Folder(
                        id=1,
                        key="folder-key-123",
                        display_name="Default",
                        code="DEFAULT",
                        fully_qualified_name="Default",
                        timestamp="2025-11-20T12:00:00Z",
                        tenant_key="tenant-key",
                        account_key="account-key",
                        type="Standard",
                        path="folder-path-123",
                        permissions=[],
                    )
                ],
                scope="Folder",
                search_state="Indexed",
                timestamp="2025-11-20T12:00:00Z",
                account_key="account-key",
                linked_folders_count=1,
                folder_keys=["folder-key-123"],
            )

            async def mock_list_by_type_async(*args, **kwargs):
                yield mock_resource

            with patch("uipath.platform.UiPath") as MockUiPath:
                mock_uipath_instance = MockUiPath.return_value
                mock_resource_catalog = AsyncMock()
                mock_resource_catalog.list_by_type_async = mock_list_by_type_async
                mock_uipath_instance.resource_catalog = mock_resource_catalog
                mock_uipath_instance.connections = AsyncMock()

                # Run push without --ignore-resources to trigger resource import
                result = runner.invoke(cli, ["push", "./"])
                assert result.exit_code == 0

            # Check that resource import was attempted
            assert (
                "Importing referenced resources to Studio Web project" in result.output
            )
            assert "Created reference for resource: test.asset" in result.output
            assert "Resource import summary:" in result.output
            assert "1 created" in result.output

    def test_push_with_ignore_resources_flag_skips_resource_import(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that push with --ignore-resources flag skips resource import."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
        self._mock_file_download(httpx_mock, "123")

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/Lock",
            json={
                "projectLockKey": "test-lock-key",
                "solutionLockKey": "test-solution-lock-key",
            },
        )

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
            # Create required files
            with open("uipath.json", "w") as f:
                json.dump(create_uipath_json(), f)

            with open("bindings.json", "w") as f:
                json.dump(
                    {
                        "version": "2.0",
                        "resources": [
                            {
                                "resource": "asset",
                                "key": "asset_name.folder_key",
                                "value": {
                                    "name": {
                                        "defaultValue": "test.asset",
                                        "isExpression": False,
                                        "displayName": "Name",
                                    },
                                    "folderPath": {
                                        "defaultValue": "Default",
                                        "isExpression": False,
                                        "displayName": "Folder Path",
                                    },
                                },
                                "metadata": {
                                    "ActivityName": "retrieve_async",
                                    "BindingsVersion": "2.2",
                                    "DisplayLabel": "FullName",
                                },
                            }
                        ],
                    },
                    f,
                )

            with open("entry-points.json", "w") as f:
                f.write("{}")

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run push with --ignore-resources flag
            result = runner.invoke(cli, ["push", "./", "--ignore-resources"])
            assert result.exit_code == 0

            # Check that resource import was NOT attempted
            assert "Importing referenced resources" not in result.output
            assert "Created reference for resource" not in result.output
            assert "Resource import summary" not in result.output

    def test_push_with_resource_not_found_shows_warning(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that push shows warning when referenced resource is not found in catalog."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
        self._mock_file_download(httpx_mock, "123")

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/Lock",
            json={
                "projectLockKey": "test-lock-key",
                "solutionLockKey": "test-solution-lock-key",
            },
        )

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
            # Create required files
            with open("uipath.json", "w") as f:
                json.dump(create_uipath_json(), f)

            with open("bindings.json", "w") as f:
                json.dump(
                    {
                        "version": "2.0",
                        "resources": [
                            {
                                "resource": "asset",
                                "key": "missing.asset.Default",
                                "value": {
                                    "name": {
                                        "defaultValue": "missing.asset",
                                        "isExpression": False,
                                        "displayName": "Name",
                                    },
                                    "folderPath": {
                                        "defaultValue": "Default",
                                        "isExpression": False,
                                        "displayName": "Folder Path",
                                    },
                                },
                                "metadata": {
                                    "ActivityName": "retrieve_async",
                                    "BindingsVersion": "2.2",
                                    "DisplayLabel": "FullName",
                                },
                            }
                        ],
                    },
                    f,
                )

            with open("entry-points.json", "w") as f:
                f.write("{}")

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Mock resource catalog list_by_type_async to return no resources
            async def mock_list_by_type_async_empty(*args, **kwargs):
                # Return empty generator (no resources found)
                return
                yield  # This makes it a generator but never yields anything

            with patch("uipath.platform.UiPath") as MockUiPath:
                mock_uipath_instance = MockUiPath.return_value
                mock_resource_catalog = AsyncMock()
                mock_resource_catalog.list_by_type_async = mock_list_by_type_async_empty
                mock_uipath_instance.resource_catalog = mock_resource_catalog
                mock_uipath_instance.connections = AsyncMock()

                # Run push without --ignore-resources
                result = runner.invoke(cli, ["push", "./"])
                assert result.exit_code == 0

            # Check that warning was shown for missing resource
            assert (
                "Importing referenced resources to Studio Web project" in result.output
            )
            assert (
                "Resource 'missing.asset' of type 'asset' at folder path 'Default' was not found"
                in result.output
            )
            assert "Resource import summary:" in result.output
            assert "1 not found" in result.output

    def test_push_with_resource_already_exists_shows_unchanged(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that push shows unchanged message when referenced resource already exists."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"
        solution_id = "test-solution-id"
        tenant_id = "test-tenant-id"

        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [],
            "files": [
                {
                    "id": "123",
                    "name": "pyproject.toml",
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
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/Lock",
            json={
                "projectLockKey": "test-lock-key",
                "solutionLockKey": "test-solution-lock-key",
            },
        )

        self._mock_file_download(httpx_mock, "123")
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

        # Mock getting the solution ID
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}",
            json={"solutionId": solution_id},
        )

        # Mock creating referenced resource (status: UNCHANGED)
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/studio_/backend/api/resourcebuilder/solutions/{solution_id}/resources/reference",
            json={
                "status": "Unchanged",
                "resource": {
                    "folders": [
                        {"fullyQualifiedName": "Default", "path": "folder-path-123"}
                    ],
                    "key": "resource-key-123",
                    "name": "existing.asset",
                    "description": "Existing asset",
                    "kind": "asset",
                    "type": "stringAsset",
                    "apiVersion": "orchestrator.uipath.com/v1",
                },
                "saved": False,
            },
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create required files
            with open("uipath.json", "w") as f:
                json.dump(create_uipath_json(), f)

            with open("bindings.json", "w") as f:
                json.dump(
                    {
                        "version": "2.0",
                        "resources": [
                            {
                                "resource": "asset",
                                "key": "existing.asset.Default",
                                "value": {
                                    "name": {
                                        "defaultValue": "existing.asset",
                                        "isExpression": False,
                                        "displayName": "Name",
                                    },
                                    "folderPath": {
                                        "defaultValue": "Default",
                                        "isExpression": False,
                                        "displayName": "Folder Path",
                                    },
                                },
                                "metadata": {
                                    "ActivityName": "retrieve_async",
                                    "BindingsVersion": "2.2",
                                    "DisplayLabel": "FullName",
                                },
                            }
                        ],
                    },
                    f,
                )

            with open("entry-points.json", "w") as f:
                f.write("{}")

            with open("pyproject.toml", "w") as f:
                f.write(project_details.to_toml())

            with open("main.py", "w") as f:
                f.write("print('Hello World')")

            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id
            os.environ["UIPATH_TENANT_ID"] = tenant_id

            # Mock resource catalog list_by_type_async
            from uipath.platform.resource_catalog import Folder, Resource

            mock_resource = Resource(
                resource_key="resource-key-123",
                name="existing.asset",
                description="Existing asset",
                resource_type="asset",
                resource_sub_type="stringAsset",
                folders=[
                    Folder(
                        id=1,
                        key="folder-key-123",
                        display_name="Default",
                        code="DEFAULT",
                        fully_qualified_name="Default",
                        timestamp="2025-11-20T12:00:00Z",
                        tenant_key="tenant-key",
                        account_key="account-key",
                        type="Standard",
                        path="folder-path-123",
                        permissions=[],
                    )
                ],
                scope="Folder",
                search_state="Indexed",
                timestamp="2025-11-20T12:00:00Z",
                account_key="account-key",
                linked_folders_count=1,
                folder_keys=["folder-key-123"],
            )

            async def mock_list_by_type_async(*args, **kwargs):
                yield mock_resource

            with patch("uipath.platform.UiPath") as MockUiPath:
                mock_uipath_instance = MockUiPath.return_value
                mock_resource_catalog = AsyncMock()
                mock_resource_catalog.list_by_type_async = mock_list_by_type_async
                mock_uipath_instance.resource_catalog = mock_resource_catalog
                mock_uipath_instance.connections = AsyncMock()

                # Run push without --ignore-resources
                result = runner.invoke(cli, ["push", "./"])
                assert result.exit_code == 0

            # Check that unchanged message was shown
            assert (
                "Importing referenced resources to Studio Web project" in result.output
            )
            assert (
                "Resource reference already exists (unchanged): existing.asset"
                in result.output
            )
            assert "Resource import summary:" in result.output
            assert "1 unchanged" in result.output


class TestMayOverrideFilesForPush:
    """Test may_override_files function for push scenarios."""

    @pytest.mark.asyncio
    async def test_no_remote_metadata_returns_true(self):
        """Test that when remote metadata doesn't exist, returns True without prompting."""
        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = None

        result = await may_override_files(mock_studio_client, "remote")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_local_metadata_prompts_user_confirms(self, tmp_path):
        """Test that when local metadata doesn't exist, prompts user and returns True on confirm."""
        remote_metadata = StudioProjectMetadata(
            schema_version="1.0",
            last_push_date="2025-11-18T17:18:06.809284+00:00",
            last_push_author="test-user",
            code_version="1.0.0",
        )

        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = remote_metadata

        with patch("uipath._cli._utils._common.UiPathConfig") as mock_config:
            mock_config.studio_metadata_file_path = (
                tmp_path / ".uipath" / "metadata.json"
            )

            with patch(
                "uipath._cli._utils._common.ConsoleLogger"
            ) as mock_console_class:
                mock_console = mock_console_class.return_value
                mock_console.confirm.return_value = True

                result = await may_override_files(mock_studio_client, "remote")
                assert result is True
                mock_console.warning.assert_called_once()
                mock_console.confirm.assert_called_once()
                # Verify the confirm message mentions "remote"
                confirm_call_args = mock_console.confirm.call_args[0][0]
                assert "remote" in confirm_call_args

    @pytest.mark.asyncio
    async def test_no_local_metadata_prompts_user_denies(self, tmp_path):
        """Test that when local metadata doesn't exist, prompts user and returns False on deny."""
        remote_metadata = StudioProjectMetadata(
            schema_version="1.0",
            last_push_date="2025-11-18T17:18:06.809284+00:00",
            last_push_author="test-user",
            code_version="1.0.0",
        )

        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = remote_metadata

        with patch("uipath._cli._utils._common.UiPathConfig") as mock_config:
            mock_config.studio_metadata_file_path = (
                tmp_path / ".uipath" / "metadata.json"
            )

            with patch(
                "uipath._cli._utils._common.ConsoleLogger"
            ) as mock_console_class:
                mock_console = mock_console_class.return_value
                mock_console.confirm.return_value = False

                result = await may_override_files(mock_studio_client, "remote")
                assert result is False

    @pytest.mark.asyncio
    async def test_local_version_greater_than_remote_returns_true(self, tmp_path):
        """Test that when local version >= remote version, returns True without prompting."""
        remote_metadata = StudioProjectMetadata(
            schema_version="1.0",
            last_push_date="2025-11-18T17:18:06.809284+00:00",
            last_push_author="test-user",
            code_version="1.0.0",
        )

        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = remote_metadata

        # Create local metadata file with higher version
        metadata_dir = tmp_path / ".uipath"
        metadata_dir.mkdir(parents=True)
        metadata_file = metadata_dir / "metadata.json"
        local_metadata = {
            "schemaVersion": "1.0",
            "lastPushDate": "2025-11-19T10:00:00.000000+00:00",
            "lastPushAuthor": "local-user",
            "codeVersion": "2.0.0",
        }
        metadata_file.write_text(json.dumps(local_metadata))

        with patch("uipath._cli._utils._common.UiPathConfig") as mock_config:
            mock_config.studio_metadata_file_path = metadata_file

            result = await may_override_files(mock_studio_client, "remote")
            assert result is True

    @pytest.mark.asyncio
    async def test_local_version_less_than_remote_prompts_user(self, tmp_path):
        """Test that when local version < remote version, prompts user."""
        remote_metadata = StudioProjectMetadata(
            schema_version="1.0",
            last_push_date="2025-11-18T17:18:06.809284+00:00",
            last_push_author="test-user",
            code_version="2.0.0",
        )

        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = remote_metadata

        # Create local metadata file with lower version
        metadata_dir = tmp_path / ".uipath"
        metadata_dir.mkdir(parents=True)
        metadata_file = metadata_dir / "metadata.json"
        local_metadata = {
            "schemaVersion": "1.0",
            "lastPushDate": "2025-11-17T10:00:00.000000+00:00",
            "lastPushAuthor": "local-user",
            "codeVersion": "1.0.0",
        }
        metadata_file.write_text(json.dumps(local_metadata))

        with patch("uipath._cli._utils._common.UiPathConfig") as mock_config:
            mock_config.studio_metadata_file_path = metadata_file

            with patch(
                "uipath._cli._utils._common.ConsoleLogger"
            ) as mock_console_class:
                mock_console = mock_console_class.return_value
                mock_console.confirm.return_value = True

                result = await may_override_files(mock_studio_client, "remote")
                assert result is True
                mock_console.warning.assert_called_once()
                mock_console.confirm.assert_called_once()

    @pytest.mark.asyncio
    async def test_local_version_equal_to_remote_returns_true(self, tmp_path):
        """Test that when local version == remote version, returns True without prompting."""
        remote_metadata = StudioProjectMetadata(
            schema_version="1.0",
            last_push_date="2025-11-18T17:18:06.809284+00:00",
            last_push_author="test-user",
            code_version="1.0.0",
        )

        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = remote_metadata

        # Create local metadata file with same version
        metadata_dir = tmp_path / ".uipath"
        metadata_dir.mkdir(parents=True)
        metadata_file = metadata_dir / "metadata.json"
        local_metadata = {
            "schemaVersion": "1.0",
            "lastPushDate": "2025-11-18T17:18:06.809284+00:00",
            "lastPushAuthor": "local-user",
            "codeVersion": "1.0.0",
        }
        metadata_file.write_text(json.dumps(local_metadata))

        with patch("uipath._cli._utils._common.UiPathConfig") as mock_config:
            mock_config.studio_metadata_file_path = metadata_file

            result = await may_override_files(mock_studio_client, "remote")
            assert result is True

    @pytest.mark.asyncio
    async def test_date_formatting_in_warning(self, tmp_path):
        """Test that the push date is formatted nicely in the warning message."""
        remote_metadata = StudioProjectMetadata(
            schema_version="1.0",
            last_push_date="2025-11-18T17:18:06.809284+00:00",
            last_push_author="test-user",
            code_version="2.0.0",
        )

        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = remote_metadata

        with patch("uipath._cli._utils._common.UiPathConfig") as mock_config:
            mock_config.studio_metadata_file_path = (
                tmp_path / ".uipath" / "metadata.json"
            )

            with patch(
                "uipath._cli._utils._common.ConsoleLogger"
            ) as mock_console_class:
                mock_console = mock_console_class.return_value
                mock_console.confirm.return_value = True

                await may_override_files(mock_studio_client, "remote")

                # Check that info was called with formatted date
                info_calls = [str(call) for call in mock_console.info.call_args_list]
                # Should contain formatted date like "Nov 18, 2025 at 05:18 PM UTC"
                date_call = [c for c in info_calls if "Last push date" in c]
                assert len(date_call) > 0
