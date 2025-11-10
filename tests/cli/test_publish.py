import json
import os
import urllib.parse
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pytest_httpx import HTTPXMock

from uipath._cli import cli


@pytest.fixture
def mock_feeds_response() -> list[tuple[str, str]]:
    """Fixture to provide mock feeds response."""
    return [
        ("Tenant Feed", "tenant_feed_id"),
        ("other Feed", "other_feed_id"),
        ("My workspace Feed", "my_workspace_feed_id"),
    ]


def _create_env_file(mock_env_vars: dict[str, str]):
    """Create the environment file."""
    with open(".env", "w") as f:
        for key, value in mock_env_vars.items():
            f.write(f"{key}={value}\n")


class TestPublish:
    def test_publish_no_env(
        self,
        runner: CliRunner,
        temp_dir: str,
    ) -> None:
        """Test publish command when no env file exists."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["publish"])
            assert result.exit_code == 1
            assert "Missing required environment variables." in result.output
            assert "UIPATH_URL" in result.output
            assert "UIPATH_ACCESS_TOKEN" in result.output

    def test_publish_no_package(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        mock_feeds_response: list[tuple[str, str]],
    ) -> None:
        """Test publish command when no package exists."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch(
                    "uipath._cli.cli_publish.get_available_feeds"
                ) as get_available_feeds_mock,
                patch("uipath._cli.cli_publish.console.prompt") as mock_prompt,
            ):
                get_available_feeds_mock.return_value = mock_feeds_response
                mock_prompt.return_value = 0
                _create_env_file(mock_env_vars)
                os.makedirs(".uipath")
                result = runner.invoke(cli, ["publish"])
                assert result.exit_code == 1
                assert (
                    "No .nupkg files found. Please run `uipath pack` first."
                    in result.output
                )

    def test_publish_invalid_feed(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        mock_feeds_response: list[tuple[str, str]],
    ) -> None:
        """Test publish command with invalid feed selections."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch(
                    "uipath._cli.cli_publish.get_available_feeds"
                ) as get_available_feeds_mock,
                patch("uipath._cli.cli_publish.console.prompt") as mock_prompt,
            ):
                get_available_feeds_mock.return_value = mock_feeds_response
                _create_env_file(mock_env_vars)
                # negative value
                mock_prompt.return_value = -1
                result = runner.invoke(cli, ["publish"])
                assert result.exit_code == 1
                assert "Invalid feed selected" in result.output
                # invalid type
                mock_prompt.return_value = "string"
                result = runner.invoke(cli, ["publish"])
                assert result.exit_code == 1
                assert type(result.exception) is TypeError
                # index error
                mock_prompt.return_value = len(mock_feeds_response) + 1
                result = runner.invoke(cli, ["publish"])
                assert result.exit_code == 1
                assert "Invalid feed selected" in result.output

    def test_publish_error(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful publish to tenant feed."""
        base_url = mock_env_vars.get("UIPATH_URL")
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()",
            status_code=401,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            # Create dummy package
            with open(os.path.join(".uipath", "test.1.0.0.nupkg"), "wb") as f:
                f.write(b"dummy package content")

            _create_env_file(mock_env_vars)

            result = runner.invoke(cli, ["publish", "--tenant"])

            assert result.exit_code == 1
            assert "Failed to publish package. Status code: 401" in result.output

    def test_publish_tenant_feed_success(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful publish to tenant feed."""
        base_url = mock_env_vars.get("UIPATH_URL")
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            # Create dummy package
            with open(os.path.join(".uipath", "test.1.0.0.nupkg"), "wb") as f:
                f.write(b"dummy package content")

            _create_env_file(mock_env_vars)

            result = runner.invoke(cli, ["publish", "--tenant"])

            assert result.exit_code == 0
            assert "Package published successfully!" in result.output

    def test_publish_folder_feed_success(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
        mock_feeds_response: list[tuple[str, str]],
    ) -> None:
        """Test successful publish to a folder feed."""
        base_url = mock_env_vars.get("UIPATH_URL")
        folder_feed_name, folder_feed_id = mock_feeds_response[1]  # Unpack the tuple

        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()?feedId={folder_feed_id}",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            # Create dummy package
            with open(os.path.join(".uipath", "test.1.0.0.nupkg"), "wb") as f:
                f.write(b"dummy package content")

            with (
                patch("uipath._cli.cli_publish.console.prompt") as mock_prompt,
                patch("uipath._cli.cli_publish.get_available_feeds") as mock_feeds,
                patch(
                    "uipath._cli.cli_publish.get_personal_workspace_info_async"
                ) as mock_workspace,
            ):
                mock_prompt.return_value = 1  # Select second feed (index 1)
                mock_feeds.return_value = mock_feeds_response
                mock_workspace.return_value = (
                    "different-feed-id",
                    "folder-id",
                )  # Different from our target feed
                _create_env_file(mock_env_vars)

                result = runner.invoke(cli, ["publish"])

                assert result.exit_code == 0
                assert "Package published successfully!" in result.output

                # Verify the methods were called correctly
                mock_prompt.assert_called_once_with("Select feed number", type=int)
                mock_feeds.assert_called_once()
                mock_workspace.assert_called_once()

    def test_publish_personal_workspace_not_found(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
    ) -> None:
        """Test publish to personal workspace when workspace not found."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            # Create dummy package
            with open(os.path.join(".uipath", "test.1.0.0.nupkg"), "wb") as f:
                f.write(b"dummy package content")

            with patch(
                "uipath._cli.cli_publish.get_personal_workspace_info_async"
            ) as mock_workspace:
                _create_env_file(mock_env_vars)
                mock_workspace.return_value = (None, None)

                result = runner.invoke(cli, ["publish", "--my-workspace"])

                assert result.exit_code == 1
                assert "No personal workspace found for user" in result.output

    def test_publish_my_workspace_feed_success(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful publish to tenant feed."""
        my_workspace_feed_id = "042e669a-c95f-46a3-87b0-9e5a98d7cf8a"
        release_id = "123"
        package_name = "mock_package_name"
        package_version = "mock__package_version"
        my_workspace_folder_id = "123"
        upload_package_response_data = {
            "value": [
                {"Body": f'{{"Id":"{package_name}","Version":"{package_version}"}}'}
            ]
        }
        list_release_response_data = {
            "value": [
                {
                    "ProcessVersion": package_version,
                    "Id": release_id,
                    "Key": "9d17b737-1283-4ebe-b1f5-7d88967b94e4",
                }
            ]
        }
        personal_workspace_response_data = {
            "PersonalWorskpaceFeedId": my_workspace_feed_id,
            "PersonalWorkspace": {"Id": my_workspace_folder_id},
        }
        base_url = mock_env_vars.get("UIPATH_URL")
        # upload package
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()?feedId={my_workspace_feed_id}",
            status_code=200,
            text=json.dumps(upload_package_response_data),
        )
        odata_top_filter = 25
        # get release info
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases?$select=Id,Key,ProcessVersion&$top={odata_top_filter}&$filter=ProcessKey%20eq%20%27{urllib.parse.quote(package_name)}%27",
            status_code=200,
            text=json.dumps(list_release_response_data),
        )
        # get personal workspace info
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended?$expand=PersonalWorkspace",
            status_code=200,
            text=json.dumps(personal_workspace_response_data),
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            # Create dummy package
            with open(
                os.path.join(".uipath", f"{package_name}.{package_version}.nupkg"), "wb"
            ) as f:
                f.write(b"dummy package content")

            _create_env_file(mock_env_vars)

            result = runner.invoke(cli, ["publish", "--my-workspace"])
            expected_release_url = f"{base_url}/orchestrator_/processes/{release_id}/edit?fid={my_workspace_folder_id}"
            assert result.exit_code == 0
            assert "Package published successfully!" in result.output
            assert expected_release_url in result.output
            assert (
                "Use the link above to configure any environment variables"
                in result.output
            )

    def test_publish_my_workspace_feed_without_flag(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test successful publish to tenant feed."""
        my_workspace_feed_id = "042e669a-c95f-46a3-87b0-9e5a98d7cf8a"
        release_id = "123"
        package_name = "mock_package_name"
        package_version = "mock__package_version"
        my_workspace_folder_id = "123"
        upload_package_response_data = {
            "value": [
                {"Body": f'{{"Id":"{package_name}","Version":"{package_version}"}}'}
            ]
        }
        list_release_response_data = {
            "value": [
                {
                    "ProcessVersion": package_version,
                    "Id": release_id,
                    "Key": "9d17b737-1283-4ebe-b1f5-7d88967b94e4",
                }
            ]
        }
        personal_workspace_response_data = {
            "PersonalWorskpaceFeedId": my_workspace_feed_id,
            "PersonalWorkspace": {"Id": my_workspace_folder_id},
        }
        feeds_response_data = [
            {
                "name": "Tenant Feed",
                "id": "3d732cad-1406-4e58-b2c9-d18ef257f100",
                "purpose": "Processes",
            },
            {
                "name": "other Feed",
                "id": "e6d5a7d5-6bdd-4263-ac48-258a093bca01",
                "purpose": "Processes",
            },
            {
                "name": "My workspace Feed",
                "id": my_workspace_feed_id,
                "purpose": "Processes",
            },
            {
                "name": "another feed",
                "id": "e6d5a7d5-6bdd-4263-ac48-258a093bca01",
                "purpose": "other_purpose",
            },
        ]
        base_url = mock_env_vars.get("UIPATH_URL")
        # upload package
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()?feedId={my_workspace_feed_id}",
            status_code=200,
            text=json.dumps(upload_package_response_data),
        )
        odata_top_filter = 25
        # get release info
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases?$select=Id,Key,ProcessVersion&$top={odata_top_filter}&$filter=ProcessKey%20eq%20%27{urllib.parse.quote(package_name)}%27",
            status_code=200,
            text=json.dumps(list_release_response_data),
        )
        # get personal workspace info
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended?$expand=PersonalWorkspace",
            status_code=200,
            text=json.dumps(personal_workspace_response_data),
        )
        # get available feeds
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/api/PackageFeeds/GetFeeds",
            status_code=200,
            text=json.dumps(feeds_response_data),
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            # Create dummy package
            with open(
                os.path.join(".uipath", f"{package_name}.{package_version}.nupkg"), "wb"
            ) as f:
                f.write(b"dummy package content")

            with patch("uipath._cli.cli_publish.console.prompt") as mock_prompt:
                # return my workspace index
                mock_prompt.return_value = 2
                _create_env_file(mock_env_vars)

                result = runner.invoke(cli, ["publish"])
                expected_release_url = f"{base_url}/orchestrator_/processes/{release_id}/edit?fid={my_workspace_folder_id}"
                assert result.exit_code == 0
                assert "Package published successfully!" in result.output
                assert expected_release_url in result.output
                assert (
                    "Use the link above to configure any environment variables"
                    in result.output
                )

    def test_publish_with_folder_success(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
        mock_feeds_response: list[tuple[str, str]],
    ) -> None:
        """Test successful publish using --folder option."""
        base_url = mock_env_vars.get("UIPATH_URL")
        folder_feed_name, folder_feed_id = mock_feeds_response[1]

        # Mock the GetFeeds API
        feeds_response_data = [
            {"name": name, "id": id, "purpose": "Processes"}
            for name, id in mock_feeds_response
        ]
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/api/PackageFeeds/GetFeeds",
            status_code=200,
            text=json.dumps(feeds_response_data),
        )

        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()?feedId={folder_feed_id}",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            with open(os.path.join(".uipath", "test.1.0.0.nupkg"), "wb") as f:
                f.write(b"dummy package content")

            with patch(
                "uipath._cli.cli_publish.get_personal_workspace_info_async"
            ) as mock_workspace:
                mock_workspace.return_value = (
                    "different-feed-id",
                    "folder-id",
                )
                _create_env_file(mock_env_vars)

                result = runner.invoke(cli, ["publish", "--folder", folder_feed_name])

                assert result.exit_code == 0
                assert "Package published successfully!" in result.output
                assert f"Using feed: {folder_feed_name}" in result.output

    def test_publish_with_folder_not_found(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
        mock_feeds_response: list[tuple[str, str]],
    ) -> None:
        """Test publish with non-existent folder name."""
        base_url = mock_env_vars.get("UIPATH_URL")

        # Mock the GetFeeds API
        feeds_response_data = [
            {"name": name, "id": id, "purpose": "Processes"}
            for name, id in mock_feeds_response
        ]
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/api/PackageFeeds/GetFeeds",
            status_code=200,
            text=json.dumps(feeds_response_data),
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            with open(os.path.join(".uipath", "test.1.0.0.nupkg"), "wb") as f:
                f.write(b"dummy package content")

            _create_env_file(mock_env_vars)

            result = runner.invoke(cli, ["publish", "--folder", "NonExistentFolder"])

            assert result.exit_code == 1  # Exits with error when folder not found
            assert "Folder 'NonExistentFolder' not found" in result.output
            assert "Available feeds:" in result.output

    def test_publish_with_folder_core_name_match(
        self,
        runner: CliRunner,
        temp_dir: str,
        mock_env_vars: dict[str, str],
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test publish using --folder with core name (without Orchestrator prefix and Feed suffix)."""
        base_url = mock_env_vars.get("UIPATH_URL")

        # Create a realistic feed name like "Orchestrator Ion Folder Feed Feed"
        folder_feed_name = "Orchestrator Ion Folder Feed Feed"
        folder_feed_id = "ion-folder-feed-id"

        # Mock the GetFeeds API
        feeds_response_data = [
            {
                "name": "Orchestrator Tenant Processes Feed",
                "id": "tenant_feed_id",
                "purpose": "Processes",
            },
            {"name": folder_feed_name, "id": folder_feed_id, "purpose": "Processes"},
        ]
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/api/PackageFeeds/GetFeeds",
            status_code=200,
            text=json.dumps(feeds_response_data),
        )

        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()?feedId={folder_feed_id}",
            status_code=200,
        )

        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs(".uipath")
            with open(os.path.join(".uipath", "test.1.0.0.nupkg"), "wb") as f:
                f.write(b"dummy package content")

            with patch(
                "uipath._cli.cli_publish.get_personal_workspace_info_async"
            ) as mock_workspace:
                mock_workspace.return_value = (
                    "different-feed-id",
                    "folder-id",
                )
                _create_env_file(mock_env_vars)

                # Test with just the core folder name "Ion Folder Feed"
                result = runner.invoke(cli, ["publish", "--folder", "Ion Folder Feed"])

                assert result.exit_code == 0
                assert "Package published successfully!" in result.output
                assert f"Using feed: {folder_feed_name}" in result.output
