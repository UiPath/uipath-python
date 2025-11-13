# type: ignore
import json
import os
from typing import Any, Dict

from click.testing import CliRunner
from pytest_httpx import HTTPXMock
from utils.project_details import ProjectDetails
from utils.uipath_json import UiPathJson

from tests.cli.utils.common import configure_env_vars
from uipath._cli import cli


class TestPull:
    """Test pull command."""

    def test_pull_without_project_id(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
    ) -> None:
        """Test pull when UIPATH_PROJECT_ID is missing."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["pull", "./"])
            assert result.exit_code == 1
            assert "UIPATH_PROJECT_ID environment variable not found." in result.output

    def test_successful_pull(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
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
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/File/789",
            content=uipath_json_legacy.to_json().encode(),
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
                assert f.read() == uipath_json_legacy.to_json()

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
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
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
                }
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

    def test_pull_skip_override(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
        httpx_mock: HTTPXMock,
        monkeypatch: Any,
    ) -> None:
        """Test pull when user chooses not to override local files."""
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
                }
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

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create local file with different content
            local_content = "print('Local version')"
            with open("main.py", "w") as f:
                f.write(local_content)

            # Set environment variables
            configure_env_vars(mock_env_vars)
            os.environ["UIPATH_PROJECT_ID"] = project_id

            # Mock user input to reject override
            monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)

            # Run pull
            result = runner.invoke(cli, ["pull", "./"])
            assert result.exit_code == 0
            # assert "differs from remote version" in result.output
            assert "Skipped 'main.py'" in result.output

            # Verify file was NOT updated (kept local version)
            with open("main.py", "r") as f:
                assert f.read() == local_content

    def test_pull_with_api_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
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
            assert "Failed to pull UiPath project" in result.output

    def test_pull_multiple_eval_folders(
        self,
        runner: CliRunner,
        temp_dir: str,
        project_details: ProjectDetails,
        uipath_json_legacy: UiPathJson,
        mock_env_vars: Dict[str, str],
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
                }
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
