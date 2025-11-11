from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.folder_service import FolderService
from uipath._services.resource_catalog_service import ResourceCatalogService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models.resource_catalog import EntityType


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
        """Generate a mock ResourceEntity response."""
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

    class TestSearchEntities:
        def test_search_entities_with_name_filter(
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

            entities = list(service.search(name="invoice"))

            assert len(entities) == 2
            assert entities[0].name == "invoice-processor"
            assert entities[0].entity_type == "process"
            assert entities[1].name == "invoice-queue"
            assert entities[1].entity_type == "queue"

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

        def test_search_entities_with_entity_types_filter(
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

            entities = list(
                service.search(entity_types=[EntityType.ASSET, EntityType.QUEUE])
            )

            assert len(entities) == 2
            assert entities[0].entity_type == "asset"
            assert entities[1].entity_type == "queue"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert "entityTypes=asset" in str(
                sent_request.url
            ) or "entityTypes%5B%5D=asset" in str(sent_request.url)
            assert "entityTypes=queue" in str(
                sent_request.url
            ) or "entityTypes%5B%5D=queue" in str(sent_request.url)

        def test_search_entities_pagination(
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
                            "1", "entity-1", "asset"
                        ),
                        TestResourceCatalogService._mock_response(
                            "2", "entity-2", "queue"
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
                            "3", "entity-3", "process"
                        ),
                    ]
                },
            )

            entities = list(service.search(page_size=2))

            assert len(entities) == 3
            assert entities[0].name == "entity-1"
            assert entities[1].name == "entity-2"
            assert entities[2].name == "entity-3"

    class TestGetEntities:
        def test_get_entities_without_filters(
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

            entities = list(service.list())

            assert len(entities) == 2
            assert entities[0].name == "test-asset"
            assert entities[1].name == "test-queue"
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

        def test_get_entities_with_folder_path(
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

            entities = list(
                service.list(
                    folder_path="/Shared/Finance", entity_types=[EntityType.ASSET]
                )
            )

            assert len(entities) == 1
            assert entities[0].name == "finance-asset"
            mock_folder_service.retrieve_folder_key.assert_called_once_with(
                "/Shared/Finance"
            )

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            # Check for folder headers
            assert "X-UIPATH-FolderKey" in sent_request.headers

        def test_get_entities_with_entity_filters(
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

            entities = list(
                service.list(
                    entity_types=[EntityType.PROCESS, EntityType.MCP_SERVER],
                    entity_sub_types=["automation"],
                )
            )

            assert len(entities) == 1
            assert entities[0].entity_type == "process"
            assert entities[0].entity_sub_type == "automation"

        def test_get_entities_pagination(
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
                            "1", "entity-1", "asset"
                        ),
                        TestResourceCatalogService._mock_response(
                            "2", "entity-2", "queue"
                        ),
                        TestResourceCatalogService._mock_response(
                            "3", "entity-3", "process"
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
                            "4", "entity-4", "bucket"
                        ),
                    ]
                },
            )

            entities = list(service.list(page_size=3))

            assert len(entities) == 4
            assert entities[0].name == "entity-1"
            assert entities[3].name == "entity-4"

        def test_get_entities_invalid_page_size(
            self,
            service: ResourceCatalogService,
        ) -> None:
            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(service.list(page_size=0))

            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(service.list(page_size=-1))

    class TestGetEntitiesByType:
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

            entities = list(service.list_by_type(entity_type=EntityType.ASSET))

            assert len(entities) == 2
            assert entities[0].name == "config-asset"
            assert entities[0].entity_type == "asset"
            assert entities[1].name == "number-asset"
            assert entities[1].entity_type == "asset"
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

            entities = list(
                service.list_by_type(entity_type=EntityType.PROCESS, name="invoice")
            )

            assert len(entities) == 1
            assert entities[0].name == "invoice-processor"
            assert entities[0].entity_type == "process"

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

            entities = list(
                service.list_by_type(
                    entity_type=EntityType.ASSET,
                    folder_path="/Shared/Finance",
                    entity_sub_types=["number"],
                )
            )

            assert len(entities) == 1
            assert entities[0].entity_sub_type == "number"
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

            entities = list(
                service.list_by_type(entity_type=EntityType.QUEUE, page_size=2)
            )

            assert len(entities) == 3
            assert all(e.entity_type == "queue" for e in entities)

        def test_list_by_type_invalid_page_size(
            self,
            service: ResourceCatalogService,
        ) -> None:
            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(service.list_by_type(entity_type=EntityType.ASSET, page_size=0))

            with pytest.raises(ValueError, match="page_size must be greater than 0"):
                list(service.list_by_type(entity_type=EntityType.ASSET, page_size=-1))

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
                            name="test-entity",
                            entity_type="asset",
                        )
                    ]
                },
            )

            entities = []
            async for entity in service.search_async(name="test"):
                entities.append(entity)

            assert len(entities) == 1
            assert entities[0].name == "test-entity"

        @pytest.mark.asyncio
        async def test_get_entities_async(
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
                            name="async-entity",
                            entity_type="queue",
                        )
                    ]
                },
            )

            entities = []
            async for entity in service.list_async():
                entities.append(entity)

            assert len(entities) == 1
            assert entities[0].name == "async-entity"
            mock_folder_service.retrieve_folder_key_async.assert_called_once_with(None)

        @pytest.mark.asyncio
        async def test_get_entities_async_with_filters(
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

            entities = []
            async for entity in service.list_async(
                entity_types=[EntityType.ASSET],
                entity_sub_types=["text"],
                folder_path="/Test/Folder",
            ):
                entities.append(entity)

            assert len(entities) == 1
            assert entities[0].entity_sub_type == "text"
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

            entities = []
            async for entity in service.list_by_type_async(
                entity_type=EntityType.ASSET
            ):
                entities.append(entity)

            assert len(entities) == 2
            assert entities[0].name == "async-asset-1"
            assert entities[0].entity_type == "asset"
            assert entities[1].name == "async-asset-2"
            assert entities[1].entity_type == "asset"
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

            entities = []
            async for entity in service.list_by_type_async(
                entity_type=EntityType.PROCESS, name="workflow"
            ):
                entities.append(entity)

            assert len(entities) == 1
            assert entities[0].name == "workflow-processor"
            assert entities[0].entity_type == "process"

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

            entities = []
            async for entity in service.list_by_type_async(
                entity_type=EntityType.QUEUE,
                folder_path="/Production",
                entity_sub_types=["transactional"],
            ):
                entities.append(entity)

            assert len(entities) == 1
            assert entities[0].entity_sub_type == "transactional"
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

            entities = []
            async for entity in service.list_by_type_async(
                entity_type=EntityType.BUCKET, page_size=2
            ):
                entities.append(entity)

            assert len(entities) == 3
            assert all(e.entity_type == "bucket" for e in entities)
