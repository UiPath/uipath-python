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
