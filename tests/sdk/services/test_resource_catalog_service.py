from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.folder_service import FolderService
from uipath._services.resource_catalog_service import ResourceCatalogService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models.resource_catalog import ResourceType


@pytest.fixture
def mock_folder_service() -> MagicMock:
    """Mock FolderService for testing."""
    service = MagicMock(spec=FolderService)
    service.retrieve_folder_key.return_value = "test-folder-key"
    service.retrieve_folder_key_async = AsyncMock(return_value="test-folder-key")
    return service


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    mock_folder_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> ResourceCatalogService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return ResourceCatalogService(
        config=config,
        execution_context=execution_context,
        folder_service=mock_folder_service,
    )


class TestResourceCatalogService:
    @staticmethod
    def _mock_response(
        entity_id: str,
        name: str,
        entity_type: str,
        entity_sub_type: str = "default",
        description: str = "",
        folder_key: str = "test-folder-key",
        **extra_fields,
    ) -> dict[str, Any]:
        """Generate a mock Resource response."""
        response = {
            "entityKey": entity_id,
            "name": name,
            "entityType": entity_type,
            "entitySubType": entity_sub_type,
            "description": description,
            "scope": "Tenant",
            "searchState": "Available",
            "timestamp": "2024-01-01T00:00:00Z",
            "folderKey": folder_key,
            "folderKeys": [folder_key],
            "tenantKey": "test-tenant-key",
            "accountKey": "test-account-key",
            "userKey": "test-user-key",
            "tags": [],
            "folders": [],
            "linkedFoldersCount": 0,
            "dependencies": [],
        }
        response.update(extra_fields)
        return response

    class TestSearchResources:
        def test_search_resources_with_name_filter(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/Search?skip=0&take=20&name=invoice",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="invoice-processor",
                            entity_type="process",
                            entity_sub_type="automation",
                            description="Process invoice documents",
                        ),
                        TestResourceCatalogService._mock_response(
                            entity_id="2",
                            name="invoice-queue",
                            entity_type="queue",
                            entity_sub_type="transactional",
                            description="Queue for invoice processing",
                        ),
                    ]
                },
            )

            resources = list(service.search(name="invoice"))

            assert len(resources) == 2
            assert resources[0].name == "invoice-processor"
            assert resources[0].resource_type == "process"
            assert resources[1].name == "invoice-queue"
            assert resources[1].resource_type == "queue"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert "name=invoice" in str(sent_request.url)
            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ResourceCatalogService.search/{version}"
            )

        def test_search_resources_with_resource_types_filter(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/Search?skip=0&take=20&entityTypes=asset&entityTypes=queue",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="3",
                            name="config-asset",
                            entity_type="asset",
                            entity_sub_type="text",
                        ),
                        TestResourceCatalogService._mock_response(
                            entity_id="4",
                            name="work-queue",
                            entity_type="queue",
                            entity_sub_type="transactional",
                        ),
                    ]
                },
            )

            resources = list(
                service.search(resource_types=[ResourceType.ASSET, ResourceType.QUEUE])
            )

            assert len(resources) == 2
            assert resources[0].resource_type == "asset"
            assert resources[1].resource_type == "queue"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert "entityTypes=asset" in str(
                sent_request.url
            ) or "entityTypes%5B%5D=asset" in str(sent_request.url)
            assert "entityTypes=queue" in str(
                sent_request.url
            ) or "entityTypes%5B%5D=queue" in str(sent_request.url)

        def test_search_resources_pagination(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # First page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/Search?skip=0&take=2",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "1", "resource-1", "asset"
                        ),
                        TestResourceCatalogService._mock_response(
                            "2", "resource-2", "queue"
                        ),
                    ]
                },
            )
            # Second page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/Search?skip=2&take=2",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "3", "resource-3", "process"
                        ),
                    ]
                },
            )

            resources = list(service.search(page_size=2))

            assert len(resources) == 3
            assert resources[0].name == "resource-1"
            assert resources[1].name == "resource-2"
            assert resources[2].name == "resource-3"

    class TestListResources:
        def test_list_resources_without_filters(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities?skip=0&take=20",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="test-asset",
                            entity_type="asset",
                            entity_sub_type="text",
                        ),
                        TestResourceCatalogService._mock_response(
                            entity_id="2",
                            name="test-queue",
                            entity_type="queue",
                            entity_sub_type="transactional",
                        ),
                    ]
                },
            )

            resources = list(service.list())

            assert len(resources) == 2
            assert resources[0].name == "test-asset"
            assert resources[1].name == "test-queue"
            mock_folder_service.retrieve_folder_key.assert_called_once_with(None)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert str(sent_request.url).endswith("/Entities?skip=0&take=20")
            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ResourceCatalogService.list/{version}"
            )

        def test_list_resources_with_folder_path(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities?skip=0&take=20&entityTypes=asset",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="finance-asset",
                            entity_type="asset",
                            entity_sub_type="number",
                        )
                    ]
                },
            )

            resources = list(
                service.list(
                    folder_path="/Shared/Finance", resource_types=[ResourceType.ASSET]
                )
            )

            assert len(resources) == 1
            assert resources[0].name == "finance-asset"
            mock_folder_service.retrieve_folder_key.assert_called_once_with(
                "/Shared/Finance"
            )

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert "X-UIPATH-FolderKey" in sent_request.headers

        def test_list_resources_with_resource_filters(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities?skip=0&take=20&entityTypes=process&entityTypes=mcpserver&entitySubType=automation",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="automation-process",
                            entity_type="process",
                            entity_sub_type="automation",
                        )
                    ]
                },
            )

            resources = list(
                service.list(
                    resource_types=[ResourceType.PROCESS, ResourceType.MCP_SERVER],
                    resource_sub_types=["automation"],
                )
            )

            assert len(resources) == 1
            assert resources[0].resource_type == "process"
            assert resources[0].resource_sub_type == "automation"

        def test_list_resources_pagination(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # First page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities?skip=0&take=3",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "1", "resource-1", "asset"
                        ),
                        TestResourceCatalogService._mock_response(
                            "2", "resource-2", "queue"
                        ),
                        TestResourceCatalogService._mock_response(
                            "3", "resource-3", "process"
                        ),
                    ]
                },
            )
            # Second page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities?skip=3&take=3",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "4", "resource-4", "bucket"
                        ),
                    ]
                },
            )

            resources = list(service.list(page_size=3))

            assert len(resources) == 4
            assert resources[0].name == "resource-1"
            assert resources[3].name == "resource-4"

        def test_list_resources_invalid_page_size(
            self,
            service: ResourceCatalogService,
        ) -> None:
            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(service.list(page_size=0))

            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(service.list(page_size=-1))

    class TestListResourcesByType:
        def test_list_by_type_basic(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/asset?skip=0&take=20",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="config-asset",
                            entity_type="asset",
                            entity_sub_type="text",
                        ),
                        TestResourceCatalogService._mock_response(
                            entity_id="2",
                            name="number-asset",
                            entity_type="asset",
                            entity_sub_type="number",
                        ),
                    ]
                },
            )

            resources = list(service.list_by_type(resource_type=ResourceType.ASSET))

            assert len(resources) == 2
            assert resources[0].name == "config-asset"
            assert resources[0].resource_type == "asset"
            assert resources[1].name == "number-asset"
            assert resources[1].resource_type == "asset"
            mock_folder_service.retrieve_folder_key.assert_called_once_with(None)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert str(sent_request.url).endswith("/Entities/asset?skip=0&take=20")
            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ResourceCatalogService.list_by_type/{version}"
            )

        def test_list_by_type_with_name_filter(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/process?skip=0&take=20&name=invoice",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="invoice-processor",
                            entity_type="process",
                            entity_sub_type="automation",
                        )
                    ]
                },
            )

            resources = list(
                service.list_by_type(resource_type=ResourceType.PROCESS, name="invoice")
            )

            assert len(resources) == 1
            assert resources[0].name == "invoice-processor"
            assert resources[0].resource_type == "process"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert "name=invoice" in str(sent_request.url)

        def test_list_by_type_with_folder_and_subtype(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/asset?skip=0&take=20&entitySubType=number",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="finance-number",
                            entity_type="asset",
                            entity_sub_type="number",
                        )
                    ]
                },
            )

            resources = list(
                service.list_by_type(
                    resource_type=ResourceType.ASSET,
                    folder_path="/Shared/Finance",
                    resource_sub_types=["number"],
                )
            )

            assert len(resources) == 1
            assert resources[0].resource_sub_type == "number"
            mock_folder_service.retrieve_folder_key.assert_called_once_with(
                "/Shared/Finance"
            )

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert "entitySubType=number" in str(sent_request.url)
            assert "X-UIPATH-FolderKey" in sent_request.headers

        def test_list_by_type_pagination(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # First page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/queue?skip=0&take=2",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "1", "queue-1", "queue"
                        ),
                        TestResourceCatalogService._mock_response(
                            "2", "queue-2", "queue"
                        ),
                    ]
                },
            )
            # Second page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/queue?skip=2&take=2",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "3", "queue-3", "queue"
                        ),
                    ]
                },
            )

            resources = list(
                service.list_by_type(resource_type=ResourceType.QUEUE, page_size=2)
            )

            assert len(resources) == 3
            assert all(r.resource_type == "queue" for r in resources)

        def test_list_by_type_invalid_page_size(
            self,
            service: ResourceCatalogService,
        ) -> None:
            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(
                    service.list_by_type(resource_type=ResourceType.ASSET, page_size=0)
                )

            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(
                    service.list_by_type(resource_type=ResourceType.ASSET, page_size=-1)
                )

    class TestAsyncMethods:
        @pytest.mark.asyncio
        async def test_search_async(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/Search?skip=0&take=20&name=test",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="test-resource",
                            entity_type="asset",
                        )
                    ]
                },
            )

            resources = []
            async for resource in service.search_async(name="test"):
                resources.append(resource)

            assert len(resources) == 1
            assert resources[0].name == "test-resource"

        @pytest.mark.asyncio
        async def test_list_resources_async(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities?skip=0&take=20",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="async-resource",
                            entity_type="queue",
                        )
                    ]
                },
            )

            resources = []
            async for resource in service.list_async():
                resources.append(resource)

            assert len(resources) == 1
            assert resources[0].name == "async-resource"
            mock_folder_service.retrieve_folder_key_async.assert_called_once_with(None)

        @pytest.mark.asyncio
        async def test_list_resources_async_with_filters(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities?skip=0&take=20&entityTypes=asset&entitySubType=text",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="text-asset",
                            entity_type="asset",
                            entity_sub_type="text",
                        )
                    ]
                },
            )

            resources = []
            async for resource in service.list_async(
                resource_types=[ResourceType.ASSET],
                resource_sub_types=["text"],
                folder_path="/Test/Folder",
            ):
                resources.append(resource)

            assert len(resources) == 1
            assert resources[0].resource_sub_type == "text"
            mock_folder_service.retrieve_folder_key_async.assert_called_once_with(
                "/Test/Folder"
            )

        @pytest.mark.asyncio
        async def test_list_by_type_async_basic(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/asset?skip=0&take=20",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="async-asset-1",
                            entity_type="asset",
                            entity_sub_type="text",
                        ),
                        TestResourceCatalogService._mock_response(
                            entity_id="2",
                            name="async-asset-2",
                            entity_type="asset",
                            entity_sub_type="number",
                        ),
                    ]
                },
            )

            resources = []
            async for resource in service.list_by_type_async(
                resource_type=ResourceType.ASSET
            ):
                resources.append(resource)

            assert len(resources) == 2
            assert resources[0].name == "async-asset-1"
            assert resources[0].resource_type == "asset"
            assert resources[1].name == "async-asset-2"
            assert resources[1].resource_type == "asset"
            mock_folder_service.retrieve_folder_key_async.assert_called_once_with(None)

        @pytest.mark.asyncio
        async def test_list_by_type_async_with_name_filter(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/process?skip=0&take=20&name=workflow",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="workflow-processor",
                            entity_type="process",
                            entity_sub_type="automation",
                        )
                    ]
                },
            )

            resources = []
            async for resource in service.list_by_type_async(
                resource_type=ResourceType.PROCESS, name="workflow"
            ):
                resources.append(resource)

            assert len(resources) == 1
            assert resources[0].name == "workflow-processor"
            assert resources[0].resource_type == "process"

        @pytest.mark.asyncio
        async def test_list_by_type_async_with_folder_and_subtype(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/queue?skip=0&take=20&entitySubType=transactional",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            entity_id="1",
                            name="transactional-queue",
                            entity_type="queue",
                            entity_sub_type="transactional",
                        )
                    ]
                },
            )

            resources = []
            async for resource in service.list_by_type_async(
                resource_type=ResourceType.QUEUE,
                folder_path="/Production",
                resource_sub_types=["transactional"],
            ):
                resources.append(resource)

            assert len(resources) == 1
            assert resources[0].resource_sub_type == "transactional"
            mock_folder_service.retrieve_folder_key_async.assert_called_once_with(
                "/Production"
            )

        @pytest.mark.asyncio
        async def test_list_by_type_async_pagination(
            self,
            httpx_mock: HTTPXMock,
            service: ResourceCatalogService,
            mock_folder_service: MagicMock,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # First page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/bucket?skip=0&take=2",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "1", "bucket-1", "bucket"
                        ),
                        TestResourceCatalogService._mock_response(
                            "2", "bucket-2", "bucket"
                        ),
                    ]
                },
            )
            # Second page
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/resourcecatalog_/Entities/bucket?skip=2&take=2",
                status_code=200,
                json={
                    "value": [
                        TestResourceCatalogService._mock_response(
                            "3", "bucket-3", "bucket"
                        ),
                    ]
                },
            )

            resources = []
            async for resource in service.list_by_type_async(
                resource_type=ResourceType.BUCKET, page_size=2
            ):
                resources.append(resource)

            assert len(resources) == 3
            assert all(r.resource_type == "bucket" for r in resources)
