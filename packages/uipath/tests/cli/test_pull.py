# type: ignore
import json
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from pytest_httpx import HTTPXMock
from utils.project_details import ProjectDetails

from tests.cli.utils.common import configure_env_vars
from uipath._cli import cli
from uipath._cli._utils._common import may_override_files
from uipath._cli._utils._studio_project import StudioProjectMetadata
from uipath.platform.errors import EnrichedException


def create_uipath_json(functions: dict[str, str] | None = None):
    """Helper to create uipath.json with functions structure."""
    if functions is None:
        functions = {"main": "main.py:main"}
    return {"functions": functions}


class TestPull:
    """Test pull command."""

    def test_pull_without_project_id(
        self,
        runner: CliRunner,
        temp_dir: str,
    ) -> None:
        """Test pull when UIPATH_PROJECT_ID is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["pull", "./"], catch_exceptions=False, env={})
            assert result.exit_code == 1
            assert "UIPATH_PROJECT_ID environment variable not found." in result.output

    def test_successful_pull(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful project pull with various file operations."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure response
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [
                {
                    "id": "evaluations-folder-id",
                    "name": "evaluations",
                    "folders": [
                        {
                            "id": "eval-sets-id",
                            "name": "eval-sets",
                            "files": [
                                {
                                    "id": "eval-sets-file-id",
                                    "name": "test-set.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                }
                            ],
                            "folders": [],
                        },
                        {
                            "id": "evaluators-id",
                            "name": "evaluators",
                            "files": [
                                {
                                    "id": "evaluators-file-id",
                                    "name": "test-evaluator.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                }
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

        # Mock file download responses
        # For main.py
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/123",
            content=b"print('Hello World')",
        )

        # For pyproject.toml
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            content=project_details.to_toml().encode(),
        )

        # For uipath.json
        uipath_json_content = create_uipath_json({"main": "main.py:main"})
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            content=json.dumps(uipath_json_content).encode(),
        )

        # For eval-sets/test-set.json
        test_set_content = {
            "id": "02424d08-f482-4777-ac4d-233add24ee06",
            "fileName": "evaluation-set-1752568767335.json",
            "evaluatorRefs": [
                "429d73a2-a748-4554-83d7-e32dec345931",
                "bdb9f7c9-2d9e-4595-81c8-ef2a60216cb9",
            ],
            "evaluations": [],
            "name": "Evaluation Set 2",
            "batchSize": 10,
            "timeoutMinutes": 20,
            "modelSettings": [],
            "createdAt": "2025-07-15T08:39:27.335Z",
            "updatedAt": "2025-07-15T08:39:27.335Z",
        }
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/eval-sets-file-id",
            content=json.dumps(test_set_content, indent=2).encode(),
        )

        # For evaluators/test-evaluator.json
        test_evaluator_content = {
            "fileName": "evaluator-1752568815245.json",
            "id": "52b716b1-c8ef-4da8-af31-fb218d0d5499",
            "name": "Evaluator 3",
            "description": "An evaluator that judges the agent based on its run history and expected behavior",
            "type": 7,
            "category": 3,
            "prompt": "As an expert evaluator, determine how well the agent did on a scale of 0-100. Focus on if the simulation was successful and if the agent behaved according to the expected output accounting for alternative valid expressions, and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a justification, explaining briefly and concisely why you gave that score.\n----\nUserOrSyntheticInputGivenToAgent:\n{{UserOrSyntheticInput}}\n----\nSimulationInstructions:\n{{SimulationInstructions}}\n----\nExpectedAgentBehavior:\n{{ExpectedAgentBehavior}}\n----\nAgentRunHistory:\n{{AgentRunHistory}}\n",
            "targetOutputKey": "*",
            "createdAt": "2025-07-15T08:40:15.245Z",
            "updatedAt": "2025-07-15T08:40:15.245Z",
        }

        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/evaluators-file-id",
            content=json.dumps(test_evaluator_content, indent=2).encode(),
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Run pull
            result = runner.invoke(cli, ["pull", "./"])
            assert result.exit_code == 0

            # Verify source code files
            assert "Downloaded 'main.py'" in result.output
            assert "Downloaded 'pyproject.toml'" in result.output
            assert "Downloaded 'uipath.json'" in result.output

            # Verify source code file contents
            with open("main.py", "r") as f:
                assert f.read() == "print('Hello World')"
            with open("pyproject.toml", "r") as f:
                assert f.read() == project_details.to_toml()
            with open("uipath.json", "r") as f:
                assert json.load(f) == uipath_json_content

            # Verify evals folder structure exists
            assert os.path.isdir("evaluations")
            assert os.path.isdir("evaluations/eval-sets")
            assert os.path.isdir("evaluations/evaluators")

            # Verify eval files exist and have correct content
            with open("evaluations/eval-sets/test-set.json", "r") as f:
                assert json.load(f) == test_set_content
            with open("evaluations/evaluators/test-evaluator.json", "r") as f:
                assert json.load(f) == test_evaluator_content

    def test_pull_with_existing_files(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
        monkeypatch: Any,
    ) -> None:
        """Test pull when local files exist and differ from remote."""
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

        # Mock file download response
        remote_content = "print('Remote version')"
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/123",
            content=remote_content.encode(),
        )

        remote_content_toml = "toml content"
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            content=remote_content_toml.encode(),
        )
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create local file with different content
            local_content = "print('Local version')"
            with open("main.py", "w") as f:
                f.write(local_content)

            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Mock user input to confirm override
            monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)

            # Run pull
            result = runner.invoke(cli, ["pull", "./"])
            assert result.exit_code == 0
            # assert "differs from remote version" in result.output
            assert "Updated 'main.py'" in result.output

            # Verify file was updated
            with open("main.py", "r") as f:
                assert f.read() == remote_content

    def test_pull_with_api_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test pull when API request fails."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock API error response
        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            status_code=401,
            json={"message": "Unauthorized"},
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["pull", "./"])
            assert result.exit_code == 1
            assert isinstance(result.exception, EnrichedException)
            assert result.exception.status_code == 401

    def test_pull_non_coded_agent_project(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test pull when the project is not a coded agent project (missing pyproject.toml)."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock a project structure WITHOUT pyproject.toml (not a coded agent project)
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
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["pull", "./"])
            assert result.exit_code == 1
            assert (
                "The targeted Studio Web project is not of type coded agent"
                in result.output
            )
            assert (
                "Please check the UIPATH_PROJECT_ID environment variable"
                in result.output
            )

    def test_pull_multiple_eval_folders(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that pull command uses evaluations folder instead of evals."""
        base_url = "https://cloud.uipath.com/organization"
        project_id = "test-project-id"

        # Mock the project structure with evaluations folder
        mock_structure = {
            "id": "root",
            "name": "root",
            "folders": [
                {
                    "id": "evaluations-id",
                    "name": "evaluations",
                    "folders": [
                        {
                            "id": "evaluators-id",
                            "name": "evaluators",
                            "files": [
                                {
                                    "id": "evaluator-1-id",
                                    "name": "contains.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                }
                            ],
                            "folders": [],
                        },
                        {
                            "id": "eval-sets-id",
                            "name": "eval-sets",
                            "files": [
                                {
                                    "id": "eval-set-1-id",
                                    "name": "default.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                }
                            ],
                            "folders": [],
                        },
                    ],
                    "files": [],
                },
                {
                    "id": "evals-id-legacy",
                    "name": "evals",
                    "folders": [
                        {
                            "id": "evaluators-id",
                            "name": "evaluators",
                            "files": [
                                {
                                    "id": "evaluator-1-id-legacy",
                                    "name": "contains.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                }
                            ],
                            "folders": [],
                        },
                        {
                            "id": "eval-sets-id",
                            "name": "eval-sets",
                            "files": [
                                {
                                    "id": "eval-set-1-id-legacy",
                                    "name": "default.json",
                                    "isMain": False,
                                    "fileType": "1",
                                    "isEntryPoint": False,
                                    "ignoredFromPublish": False,
                                }
                            ],
                            "folders": [],
                        },
                    ],
                    "files": [],
                },
            ],
            "files": [
                {
                    "id": "main-py-id",
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
            ],
            "folderType": "0",
        }

        httpx_mock.add_response(
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure",
            json=mock_structure,
        )

        # Mock file downloads
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/main-py-id",
            content=b"print('test')",
        )
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/456",
            content=b"toml content",
        )

        evaluator_content = {"version": "1.0", "name": "Contains Evaluator"}
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/evaluator-1-id",
            content=json.dumps(evaluator_content, indent=2).encode(),
        )

        eval_set_content = {"version": "1.0", "name": "Default Eval Set"}
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/eval-set-1-id",
            content=json.dumps(eval_set_content, indent=2).encode(),
        )

        evaluator_content_legacy = {
            "version": "1.0",
            "name": "Contains Evaluator legacy",
        }
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/evaluator-1-id-legacy",
            content=json.dumps(evaluator_content_legacy, indent=2).encode(),
        )

        eval_set_content_legacy = {"version": "1.0", "name": "Default Eval Set legacy"}
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/eval-set-1-id-legacy",
            content=json.dumps(eval_set_content_legacy, indent=2).encode(),
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            result = runner.invoke(cli, ["pull", "./"])
            assert result.exit_code == 0

            # Verify files from evaluations are downloaded to evaluations/ directory
            assert os.path.exists("evaluations/evaluators/contains.json")
            assert os.path.exists("evaluations/eval-sets/default.json")

            # Verify content
            with open("evaluations/evaluators/contains.json", "r") as f:
                assert json.load(f) == evaluator_content
            with open("evaluations/eval-sets/default.json", "r") as f:
                assert json.load(f) == eval_set_content

            # Verify files from evals are downloaded to evals/ directory
            assert os.path.exists("evals/evaluators/contains.json")
            assert os.path.exists("evals/eval-sets/default.json")

            # Verify content
            with open("evals/evaluators/contains.json", "r") as f:
                assert json.load(f) == evaluator_content_legacy
            with open("evals/eval-sets/default.json", "r") as f:
                assert json.load(f) == eval_set_content_legacy


class TestMayOverrideFiles:
    """Test may_override_files function for pull scenarios."""

    @pytest.mark.asyncio
    async def test_no_remote_metadata_returns_true(self):
        """Test that when remote metadata doesn't exist, returns True without prompting."""
        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = None

        result = await may_override_files(mock_studio_client, "local")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_local_metadata_prompts_user_confirms(self, tmp_path, monkeypatch):
        """Test that when local metadata doesn't exist, prompts user and returns True on confirm."""
        # Create mock remote metadata
        remote_metadata = StudioProjectMetadata(
            schema_version="1.0",
            last_push_date="2025-11-18T17:18:06.809284+00:00",
            last_push_author="test-user",
            code_version="1.0.0",
        )

        mock_studio_client = AsyncMock()
        mock_studio_client.get_project_metadata_async.return_value = remote_metadata

        # Mock UiPathConfig to return non-existent path
        with patch("uipath._cli._utils._common.UiPathConfig") as mock_config:
            mock_config.studio_metadata_file_path = (
                tmp_path / ".uipath" / "metadata.json"
            )

            # Mock console.confirm to return True
            with patch(
                "uipath._cli._utils._common.ConsoleLogger"
            ) as mock_console_class:
                mock_console = mock_console_class.return_value
                mock_console.confirm.return_value = True

                result = await may_override_files(mock_studio_client, "local")
                assert result is True
                mock_console.warning.assert_called_once()
                mock_console.confirm.assert_called_once()

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

                result = await may_override_files(mock_studio_client, "local")
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

            result = await may_override_files(mock_studio_client, "local")
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

                result = await may_override_files(mock_studio_client, "local")
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

            result = await may_override_files(mock_studio_client, "local")
            assert result is True
