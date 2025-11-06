# type: ignore
import json
import os
from functools import wraps
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from click.testing import CliRunner
from pytest_httpx import HTTPXMock

from uipath._cli import cli
from uipath._utils._bindings import ResourceOverwriteParser
from uipath.tracing import TracingManager


@pytest.fixture(autouse=True)
def mock_tracer():
    def mock_tracer_impl(**kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    TracingManager.reapply_traced_decorator(mock_tracer_impl)
    yield
    TracingManager.reapply_traced_decorator(None)


@pytest.fixture
def sample_main_script():
    """Load the sample main.py for resource overrides."""
    sample_path = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "resource-overrides"
        / "main.py"
    )
    with open(sample_path, "r") as f:
        return f.read()


@pytest.fixture
def overwrites_data():
    """Load the overwrites.json test data."""
    overwrites_path = Path(__file__).parent / "overwrites.json"
    with open(overwrites_path, "r") as f:
        return json.load(f)


@pytest.fixture
def uipath_json_with_overwrites(overwrites_data):
    """Create a uipath.json structure with resource overwrites."""
    return {
        "projectVersion": "1.0.0",
        "description": "Test project for resource overwrites",
        "runtime": {"internalArguments": {"resourceOverwrites": overwrites_data}},
    }


class TestResourceOverrides:
    """Tests for resource override functionality."""

    def _mock_calls(
        self, httpx_mock: HTTPXMock, base_url: str, org_scoped_base_url: str
    ):
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered?$filter=Name eq 'Overwritten Asset Name'&$top=1",
            status_code=200,
            json={
                "value": [
                    {
                        "Name": "Overwritten Asset Name",
                        "ValueType": "Text",
                        "StringValue": "test_value",
                    }
                ]
            },
        )

        # Mock Connections API - retrieve_async
        # Connection uses /connections_/api/v1/Connections/{key}
        httpx_mock.add_response(
            url=f"{base_url}/connections_/api/v1/Connections/overwritten-connection-id-12345",
            status_code=200,
            json={
                "Id": "overwritten-connection-id-12345",
                "Name": "Connection Name",
                "element_instance_id": 1234,
            },
        )

        # Mock Actions API - need to mock app retrieval first
        # First mock the app schema retrieval
        httpx_mock.add_response(
            url=f"{org_scoped_base_url}/apps_/default/api/v1/default/deployed-action-apps-schemas?search=Overwritten App Name",
            method="GET",
            json={
                "deployed": [
                    {
                        "systemName": "app-key-123",
                        "deploymentFolder": {
                            "fullyQualifiedName": "Overwritten/App/Folder"
                        },
                        "actionSchema": {
                            "key": "schema-key",
                            "inputs": [],
                            "outputs": [],
                            "outcomes": [],
                            "inOuts": [],
                        },
                    }
                ]
            },
        )
        # Then mock the action creation
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/tasks/AppTasks/CreateAppTask",
            method="POST",
            json={"Id": "action-id-123", "Status": "Created"},
        )

        # Mock Context Grounding API - retrieve index
        httpx_mock.add_response(
            url=f"{base_url}/ecs_/v2/indexes?$filter=Name eq 'Overwritten Index Name'&$expand=dataSource",
            method="GET",
            json={
                "value": [
                    {
                        "id": "test-index-id",
                        "name": "Overwritten Index Name",
                        "lastIngestionStatus": "Completed",
                    }
                ]
            },
        )

        # exchange folder path for folder key
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=Folder&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "Overwritten/Index/Folder",
                    }
                ]
            },
        )

        # Mock Buckets API - retrieve_async
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Buckets?$filter=Name eq 'Overwritten Bucket Name'&$top=1",
            method="GET",
            json={
                "value": [
                    {
                        "Id": 123,
                        "Name": "Overwritten Bucket Name",
                        "Identifier": "bucket-key",
                    }
                ]
            },
        )

        # Mock Processes API - invoke_async
        # First mock the release retrieval
        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            method="POST",
            json={
                "value": [
                    {
                        "Key": "test-job-key",
                        "State": "Running",
                        "StartTime": "2024-01-01T00:00:00Z",
                        "Id": 123,
                    }
                ]
            },
        )

    def _assert(self, result, httpx_mock):
        # Verify execution was successful
        assert result.exit_code == 0
        assert "Applied 6 resource overwrite(s)" in result.output

        # Now verify that overridden values were used in API calls
        # Get all requests made
        requests = httpx_mock.get_requests()

        # Check Assets call - should have overwritten name in filter
        asset_requests = [r for r in requests if "Assets" in str(r.url)]
        assert len(asset_requests) > 0
        asset_url = str(asset_requests[0].url)
        parsed_url = urlparse(asset_url)
        query_params = parse_qs(parsed_url.query)
        assert "$filter" in query_params
        # The filter should contain the overwritten name
        assert "Overwritten Asset Name" in query_params["$filter"][0]

        # Check Connections call - should have overwritten connection ID in URL
        conn_requests = [
            r for r in requests if "Connections" in str(r.url) and r.method == "GET"
        ]
        assert len(conn_requests) > 0
        assert "overwritten-connection-id-12345" in str(conn_requests[0].url)

        # Check Actions call - should have overwritten app name
        app_requests = [
            r for r in requests if "deployed-action-apps-schemas" in str(r.url)
        ]
        assert len(app_requests) > 0
        app_query = parse_qs(urlparse(str(app_requests[0].url)).query)
        assert "search" in app_query
        assert app_query["search"][0] == "Overwritten App Name"

        # Check Context Grounding call - should have overwritten index name in URL
        index_requests = [r for r in requests if "ecs_" in str(r.url)]
        assert len(index_requests) > 0
        assert "Overwritten+Index+Name" in str(index_requests[0].url)

        # Check Buckets call - should have overwritten bucket name
        bucket_requests = [
            r for r in requests if "Buckets" in str(r.url) and r.method == "GET"
        ]
        assert len(bucket_requests) > 0
        bucket_query = parse_qs(urlparse(str(bucket_requests[0].url)).query)
        # Bucket name typically in filter
        assert "$filter" in bucket_query
        assert "Overwritten Bucket Name" in bucket_query["$filter"][0]

        # Check Processes call - should have overwritten process name
        start_job_request = [r for r in requests if "StartJobs" in str(r.url)]
        assert len(start_job_request) > 0
        assert "Overwritten Process Name" in str(start_job_request[0].content)

    def test_parse_overwrites_with_type_adapter(self, overwrites_data):
        """Test that ResourceOverwriteParser correctly parses all resource types."""
        parsed_overwrites = {}

        for key, value in overwrites_data.items():
            parsed_overwrites[key] = ResourceOverwriteParser.parse(key, value)

        # Verify asset overwrite
        asset = parsed_overwrites["asset.asset_name"]
        assert asset.resource_identifier == "Overwritten Asset Name"
        assert asset.folder_identifier == "Overwritten/Asset/Folder"

        # Verify connection overwrite (uses different field names)
        connection = parsed_overwrites["connection.connection_key"]
        assert connection.resource_identifier == "overwritten-connection-id-12345"
        assert connection.folder_identifier == "overwritten-folder-key-abc"

        # Verify app overwrite
        app = parsed_overwrites["app.app_name"]
        assert app.resource_identifier == "Overwritten App Name"
        assert app.folder_identifier == "Overwritten/App/Folder"

        # Verify index overwrite
        index = parsed_overwrites["index.index_name"]
        assert index.resource_identifier == "Overwritten Index Name"
        assert index.folder_identifier == "Overwritten/Index/Folder"

        # Verify bucket overwrite
        bucket = parsed_overwrites["bucket.bucket_name"]
        assert bucket.resource_identifier == "Overwritten Bucket Name"
        assert bucket.folder_identifier == "Overwritten/Bucket/Folder"

        # Verify process overwrite
        process = parsed_overwrites["process.process_name"]
        assert process.resource_identifier == "Overwritten Process Name"
        assert process.folder_identifier == "Overwritten/Process/Folder"

    def test_run_with_resource_overwrites(
        self,
        runner: CliRunner,
        temp_dir: str,
        sample_main_script: str,
        uipath_json_with_overwrites: dict,
        httpx_mock: HTTPXMock,
    ):
        """Test that uipath run applies resource overwrites correctly."""
        entrypoint = "main.py"

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create the main.py script
            script_path = os.path.join(temp_dir, entrypoint)
            with open(script_path, "w") as f:
                f.write(sample_main_script)

            # Create __uipath directory and uipath.json with overwrites
            uipath_dir = os.path.join(temp_dir, "__uipath")
            os.makedirs(uipath_dir, exist_ok=True)
            uipath_json_path = os.path.join(uipath_dir, "uipath.json")
            with open(uipath_json_path, "w") as f:
                json.dump(uipath_json_with_overwrites, f)
            org = "test-org"
            tenant = "test-tenant"
            base_url = f"https://example.com/{org}/{tenant}"
            org_scoped_base_url = f"https://example.com/{org}"

            # Set UIPATH_JOB_KEY environment variable so overwrites are applied
            with patch.dict(
                os.environ,
                {
                    "UIPATH_JOB_KEY": "test-job-key-12345",
                    "UIPATH_URL": base_url,
                    "UIPATH_ACCESS_TOKEN": "test-access-token-12345",
                    "UIPATH_ORGANIZATION_ID": org,
                    "UIPATH_TENANT_ID": tenant,
                },
            ):
                self._mock_calls(httpx_mock, base_url, org_scoped_base_url)

                current_dir_copy = os.getcwd()
                os.chdir(temp_dir)

                # Run the CLI command
                result = runner.invoke(cli, ["run", script_path])

                # Restore cwd
                os.chdir(current_dir_copy)

                self._assert(result, httpx_mock)

    def test_debug_with_resource_overwrites(
        self,
        runner: CliRunner,
        temp_dir: str,
        sample_main_script: str,
        overwrites_data: dict,
        httpx_mock: HTTPXMock,
    ):
        """Test that uipath debug applies resource overwrites correctly."""
        entrypoint = "main.py"

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create the main.py script
            script_path = os.path.join(temp_dir, entrypoint)
            with open(script_path, "w") as f:
                f.write(sample_main_script)

            # Create minimal uipath.json for debug (overwrites come from studio client)
            with open(os.path.join(temp_dir, "uipath.json"), "w") as f:
                json.dump({"projectVersion": "1.0.0"}, f)

            org = "test-org"
            tenant = "test-tenant"
            base_url = f"https://example.com/{org}/{tenant}"
            org_scoped_base_url = f"https://example.com/{org}"

            # Set environment variables for debug mode
            with patch.dict(
                os.environ,
                {
                    "UIPATH_URL": base_url,
                    "UIPATH_ACCESS_TOKEN": "test-access-token-12345",
                    "UIPATH_ORGANIZATION_ID": org,
                    "UIPATH_TENANT_ID": tenant,
                    "UIPATH_PROJECT_ID": "test-project-id-12345",  # Required for debug mode
                },
            ):
                # Patch StudioClient to return our test overwrites
                async def mock_get_resource_overwrites():
                    """Mock implementation that returns parsed overwrites."""
                    parsed_overwrites = {}
                    for key, value in overwrites_data.items():
                        parsed_overwrites[key] = ResourceOverwriteParser.parse(
                            key, value
                        )
                    return parsed_overwrites

                with patch(
                    "uipath._cli.cli_debug.StudioClient"
                ) as mock_studio_client_class:
                    mock_studio_client = MagicMock()
                    mock_studio_client_class.return_value = mock_studio_client
                    mock_studio_client.get_resource_overwrites = (
                        mock_get_resource_overwrites
                    )

                    self._mock_calls(httpx_mock, base_url, org_scoped_base_url)

                    current_dir_copy = os.getcwd()
                    os.chdir(temp_dir)

                    # Pass 'c' to continue execution in debug mode
                    result = runner.invoke(cli, ["debug", script_path], input="c\n")

                    # Restore cwd
                    os.chdir(current_dir_copy)

                    self._assert(result, httpx_mock)
