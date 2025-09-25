import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.buckets_service import BucketsService
from uipath._services.context_grounding_service import ContextGroundingService
from uipath._services.folder_service import FolderService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models import ContextGroundingIndex, ContextGroundingQueryResponse


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> ContextGroundingService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    folders_service = FolderService(config=config, execution_context=execution_context)
    buckets_service = BucketsService(config=config, execution_context=execution_context)
    return ContextGroundingService(
        config=config,
        execution_context=execution_context,
        folders_service=folders_service,
        buckets_service=buckets_service,
    )


class TestContextGroundingService:
    def test_search(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v1/search",
            status_code=200,
            json=[
                {
                    "source": "test-source",
                    "page_number": "1",
                    "content": "Test content",
                    "metadata": {
                        "operation_id": "test-op",
                        "strategy": "test-strategy",
                    },
                    "score": 0.95,
                }
            ],
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes?$filter=Name eq 'test-index'&$expand=dataSource",
            status_code=200,
            json={
                "value": [
                    {
                        "id": "test-index-id",
                        "name": "test-index",
                        "lastIngestionStatus": "Completed",
                    }
                ]
            },
        )

        response = service.search(
            name="test-index", query="test query", number_of_results=1
        )

        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ContextGroundingQueryResponse)
        assert response[0].source == "test-source"
        assert response[0].page_number == "1"
        assert response[0].content == "Test content"
        assert response[0].metadata.operation_id == "test-op"
        assert response[0].metadata.strategy == "test-strategy"
        assert response[0].score == 0.95

        sent_requests = httpx_mock.get_requests()
        if sent_requests is None:
            raise Exception("No request was sent")

        assert sent_requests[3].method == "POST"
        assert sent_requests[3].url == f"{base_url}{org}{tenant}/ecs_/v1/search"

        assert HEADER_USER_AGENT in sent_requests[3].headers
        assert (
            sent_requests[3].headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ContextGroundingService.search/{version}"
        )

    @pytest.mark.anyio
    async def test_search_async(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v1/search",
            status_code=200,
            json=[
                {
                    "source": "test-source",
                    "page_number": "1",
                    "content": "Test content",
                    "metadata": {
                        "operation_id": "test-op",
                        "strategy": "test-strategy",
                    },
                    "score": 0.95,
                }
            ],
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes?$filter=Name eq 'test-index'&$expand=dataSource",
            status_code=200,
            json={
                "value": [
                    {
                        "id": "test-index-id",
                        "name": "test-index",
                        "lastIngestionStatus": "Completed",
                    }
                ]
            },
        )

        response = await service.search_async(
            name="test-index", query="test query", number_of_results=1
        )

        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ContextGroundingQueryResponse)
        assert response[0].source == "test-source"
        assert response[0].page_number == "1"
        assert response[0].content == "Test content"
        assert response[0].metadata.operation_id == "test-op"
        assert response[0].metadata.strategy == "test-strategy"
        assert response[0].score == 0.95

        sent_requests = httpx_mock.get_requests()
        if sent_requests is None:
            raise Exception("No request was sent")

        assert sent_requests[3].method == "POST"
        assert sent_requests[3].url == f"{base_url}{org}{tenant}/ecs_/v1/search"

        assert HEADER_USER_AGENT in sent_requests[3].headers
        assert (
            sent_requests[3].headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ContextGroundingService.search_async/{version}"
        )

    def test_retrieve(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes?$filter=Name eq 'test-index'&$expand=dataSource",
            status_code=200,
            json={
                "value": [
                    {
                        "id": "test-index-id",
                        "name": "test-index",
                        "lastIngestionStatus": "Completed",
                    }
                ]
            },
        )

        index = service.retrieve(name="test-index")

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "test-index-id"
        assert index.name == "test-index"
        assert index.last_ingestion_status == "Completed"

        sent_requests = httpx_mock.get_requests()
        if sent_requests is None:
            raise Exception("No request was sent")

        assert sent_requests[1].method == "GET"
        assert (
            sent_requests[1].url
            == f"{base_url}{org}{tenant}/ecs_/v2/indexes?%24filter=Name+eq+%27test-index%27&%24expand=dataSource"
        )

        assert HEADER_USER_AGENT in sent_requests[1].headers
        assert (
            sent_requests[1].headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ContextGroundingService.retrieve/{version}"
        )

    @pytest.mark.anyio
    async def test_retrieve_async(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes?$filter=Name eq 'test-index'&$expand=dataSource",
            status_code=200,
            json={
                "value": [
                    {
                        "id": "test-index-id",
                        "name": "test-index",
                        "lastIngestionStatus": "Completed",
                    }
                ]
            },
        )

        index = await service.retrieve_async(name="test-index")

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "test-index-id"
        assert index.name == "test-index"
        assert index.last_ingestion_status == "Completed"

        sent_requests = httpx_mock.get_requests()
        if sent_requests is None:
            raise Exception("No request was sent")

        assert sent_requests[1].method == "GET"
        assert (
            sent_requests[1].url
            == f"{base_url}{org}{tenant}/ecs_/v2/indexes?%24filter=Name+eq+%27test-index%27&%24expand=dataSource"
        )

        assert HEADER_USER_AGENT in sent_requests[1].headers
        assert (
            sent_requests[1].headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ContextGroundingService.retrieve_async/{version}"
        )

    def test_create_index_bucket(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes/create",
            status_code=200,
            json={
                "id": "new-index-id",
                "name": "test-bucket-index",
                "description": "Test bucket index",
                "lastIngestionStatus": "Queued",
                "dataSource": {"bucketName": "test-bucket", "folder": "/test/folder"},
            },
        )

        source = {
            "type": "bucket",
            "bucket_name": "test-bucket",
            "folder_path": "/test/folder",
            "directory_path": "/",
            "file_type": "pdf",
        }

        index = service.create_index(
            name="test-bucket-index",
            description="Test bucket index",
            source=source,
            advanced_ingestion=True,
        )

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "new-index-id"
        assert index.name == "test-bucket-index"
        assert index.description == "Test bucket index"
        assert index.last_ingestion_status == "Queued"

        sent_requests = httpx_mock.get_requests()
        assert len(sent_requests) == 2

        create_request = sent_requests[1]
        assert create_request.method == "POST"
        assert create_request.url == f"{base_url}{org}{tenant}/ecs_/v2/indexes/create"
        assert HEADER_USER_AGENT in create_request.headers
        assert (
            create_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ContextGroundingService.create_index/{version}"
        )

        import json

        request_data = json.loads(create_request.content)
        assert request_data["name"] == "test-bucket-index"
        assert request_data["description"] == "Test bucket index"
        assert (
            request_data["dataSource"]["@odata.type"]
            == "#UiPath.Vdbs.Domain.Api.V20Models.StorageBucketDataSourceRequest"
        )
        assert request_data["dataSource"]["bucketName"] == "test-bucket"
        assert request_data["dataSource"]["folder"] == "/test/folder"
        assert request_data["dataSource"]["directoryPath"] == "/"
        assert request_data["dataSource"]["fileNameGlob"] == "**/*.pdf"
        assert (
            request_data["preProcessing"]["@odata.type"]
            == "#UiPath.Vdbs.Domain.Api.V20Models.LLMV4PreProcessingRequest"
        )

    def test_create_index_google_drive(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes/create",
            status_code=200,
            json={
                "id": "google-index-id",
                "name": "test-google-index",
                "description": "Test Google Drive index",
                "lastIngestionStatus": "Queued",
                "dataSource": {"connectionId": "conn-123", "folder": "/test/folder"},
            },
        )

        source = {
            "type": "google_drive",
            "connection_id": "conn-123",
            "connection_name": "Google Drive Connection",
            "leaf_folder_id": "folder-456",
            "directory_path": "/shared-docs",
            "folder_path": "/test/folder",
            "file_type": "docx",
        }

        index = service.create_index(
            name="test-google-index",
            description="Test Google Drive index",
            source=source,
            cron_expression="0 0 18 ? * 2",
            time_zone_id="Pacific Standard Time",
        )

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "google-index-id"
        assert index.name == "test-google-index"

        sent_requests = httpx_mock.get_requests()
        create_request = sent_requests[1]

        import json

        request_data = json.loads(create_request.content)
        assert (
            request_data["dataSource"]["@odata.type"]
            == "#UiPath.Vdbs.Domain.Api.V20Models.GoogleDriveDataSourceRequest"
        )
        assert request_data["dataSource"]["connectionId"] == "conn-123"
        assert request_data["dataSource"]["connectionName"] == "Google Drive Connection"
        assert request_data["dataSource"]["leafFolderId"] == "folder-456"
        assert request_data["dataSource"]["directoryPath"] == "/shared-docs"
        assert request_data["dataSource"]["fileNameGlob"] == "**/*.docx"
        assert request_data["dataSource"]["indexer"]["cronExpression"] == "0 0 18 ? * 2"
        assert (
            request_data["dataSource"]["indexer"]["timeZoneId"]
            == "Pacific Standard Time"
        )

    def test_create_index_dropbox(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes/create",
            status_code=200,
            json={
                "id": "dropbox-index-id",
                "name": "test-dropbox-index",
                "lastIngestionStatus": "Queued",
            },
        )

        source = {
            "type": "dropbox",
            "connection_id": "dropbox-conn-789",
            "connection_name": "Dropbox Connection",
            "directory_path": "/company-files",
            "folder_path": "/test/folder",
        }

        index = service.create_index(
            name="test-dropbox-index", source=source, advanced_ingestion=False
        )

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "dropbox-index-id"

        sent_requests = httpx_mock.get_requests()
        create_request = sent_requests[1]

        import json

        request_data = json.loads(create_request.content)
        assert (
            request_data["dataSource"]["@odata.type"]
            == "#UiPath.Vdbs.Domain.Api.V20Models.DropboxDataSourceRequest"
        )
        assert request_data["dataSource"]["connectionId"] == "dropbox-conn-789"
        assert request_data["dataSource"]["connectionName"] == "Dropbox Connection"
        assert request_data["dataSource"]["directoryPath"] == "/company-files"
        assert request_data["dataSource"]["fileNameGlob"] == "**/*"
        assert "preProcessing" not in request_data

    def test_create_index_onedrive(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes/create",
            status_code=200,
            json={
                "id": "onedrive-index-id",
                "name": "test-onedrive-index",
                "lastIngestionStatus": "Queued",
            },
        )

        source = {
            "type": "onedrive",
            "connection_id": "onedrive-conn-101",
            "connection_name": "OneDrive Connection",
            "leaf_folder_id": "onedrive-folder-202",
            "directory_path": "/reports",
            "folder_path": "/test/folder",
            "file_type": "xlsx",
        }

        index = service.create_index(name="test-onedrive-index", source=source)

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "onedrive-index-id"

        sent_requests = httpx_mock.get_requests()
        create_request = sent_requests[1]

        import json

        request_data = json.loads(create_request.content)
        assert (
            request_data["dataSource"]["@odata.type"]
            == "#UiPath.Vdbs.Domain.Api.V20Models.OneDriveDataSourceRequest"
        )
        assert request_data["dataSource"]["connectionId"] == "onedrive-conn-101"
        assert request_data["dataSource"]["leafFolderId"] == "onedrive-folder-202"
        assert request_data["dataSource"]["fileNameGlob"] == "**/*.xlsx"

    def test_create_index_confluence(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes/create",
            status_code=200,
            json={
                "id": "confluence-index-id",
                "name": "test-confluence-index",
                "lastIngestionStatus": "Queued",
            },
        )

        source = {
            "type": "confluence",
            "connection_id": "confluence-conn-303",
            "connection_name": "Confluence Connection",
            "space_id": "space-404",
            "directory_path": "/wiki-docs",
            "folder_path": "/test/folder",
        }

        index = service.create_index(name="test-confluence-index", source=source)

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "confluence-index-id"

        sent_requests = httpx_mock.get_requests()
        create_request = sent_requests[1]

        import json

        request_data = json.loads(create_request.content)
        assert (
            request_data["dataSource"]["@odata.type"]
            == "#UiPath.Vdbs.Domain.Api.V20Models.ConfluenceDataSourceRequest"
        )
        assert request_data["dataSource"]["connectionId"] == "confluence-conn-303"
        assert request_data["dataSource"]["connectionName"] == "Confluence Connection"

    @pytest.mark.anyio
    async def test_create_index_async(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes/create",
            status_code=200,
            json={
                "id": "async-index-id",
                "name": "test-async-index",
                "description": "Test async index",
                "lastIngestionStatus": "Queued",
            },
        )

        source = {
            "type": "bucket",
            "bucket_name": "async-bucket",
            "folder_path": "/async/folder",
        }

        index = await service.create_index_async(
            name="test-async-index", description="Test async index", source=source
        )

        assert isinstance(index, ContextGroundingIndex)
        assert index.id == "async-index-id"
        assert index.name == "test-async-index"

        sent_requests = httpx_mock.get_requests()
        create_request = sent_requests[1]
        assert create_request.method == "POST"
        assert HEADER_USER_AGENT in create_request.headers
        assert (
            create_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ContextGroundingService.create_index_async/{version}"
        )

    def test_create_index_missing_bucket_name(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        source = {"type": "bucket", "folder_path": "/test/folder"}

        with pytest.raises(
            ValueError, match="bucket_name is required for bucket data source"
        ):
            service.create_index(name="test-invalid-bucket", source=source)

    def test_create_index_missing_google_drive_fields(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        source = {
            "type": "google_drive",
            "connection_id": "conn-123",
            "folder_path": "/test/folder",
        }

        with pytest.raises(
            ValueError, match="connection_name is required for Google Drive data source"
        ):
            service.create_index(name="test-invalid-google", source=source)

    def test_create_index_unsupported_source_type(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        source = {"type": "unsupported", "folder_path": "/test/folder"}

        with pytest.raises(
            ValueError, match="Unsupported data source type: unsupported"
        ):
            service.create_index(name="test-unsupported", source=source)

    def test_create_index_custom_preprocessing(
        self,
        httpx_mock: HTTPXMock,
        service: ContextGroundingService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        from uipath._utils.constants import LLMV3Mini

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/ecs_/v2/indexes/create",
            status_code=200,
            json={
                "id": "custom-prep-index-id",
                "name": "test-custom-prep-index",
                "lastIngestionStatus": "Queued",
            },
        )

        source = {
            "type": "bucket",
            "bucket_name": "test-bucket",
            "folder_path": "/test/folder",
        }

        index = service.create_index(
            name="test-custom-prep-index",
            source=source,
            preprocessing_request=LLMV3Mini,
        )

        assert isinstance(index, ContextGroundingIndex)

        sent_requests = httpx_mock.get_requests()
        create_request = sent_requests[1]

        import json

        request_data = json.loads(create_request.content)
        assert request_data["preProcessing"]["@odata.type"] == LLMV3Mini
