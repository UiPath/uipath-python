import json

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.queues_service import QueuesService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models.queues import (
    CommitType,
    QueueItem,
    QueueItemPriority,
    TransactionItem,
    TransactionItemResult,
)


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> QueuesService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return QueuesService(config=config, execution_context=execution_context)


class TestQueuesService:
    def test_list_items(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems?%24skip=0&%24top=100",
            status_code=200,
            json={
                "value": [
                    {
                        "Id": 1,
                        "Name": "test-queue",
                        "Priority": "High",
                    }
                ]
            },
        )

        items = list(service.list_items())

        assert len(items) == 1
        assert items[0].Id == 1  # Id is an extra field in the model
        assert items[0].name == "test-queue"
        assert items[0].priority == "High"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems?%24skip=0&%24top=100"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.list_items/{version}"
        )

    @pytest.mark.asyncio
    async def test_list_items_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems?%24skip=0&%24top=100",
            status_code=200,
            json={
                "value": [
                    {
                        "Id": 1,
                        "Name": "test-queue",
                        "Priority": "High",
                    }
                ]
            },
        )

        items = []
        async for item in service.list_items_async():
            items.append(item)

        assert len(items) == 1
        assert items[0].Id == 1  # Id is an extra field in the model
        assert items[0].name == "test-queue"
        assert items[0].priority == "High"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems?%24skip=0&%24top=100"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.list_items_async/{version}"
        )

    def test_create_item(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "Reference": "test-ref-001",
                "Priority": "High",
                "SpecificContent": {"key": "value"},
            },
        )

        response = service.create_item(
            queue_name="test-queue",
            reference="test-ref-001",
            specific_content={"key": "value"},
            priority="High",
        )

        # Access via model_extra since id and reference are not defined fields
        assert response.model_extra.get("Id") == 1
        assert response.name == "test-queue"
        assert response.model_extra.get("Reference") == "test-ref-001"
        assert response.priority == "High"
        assert response.specific_content == {"key": "value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem"
        )
        request_body = json.loads(sent_request.content.decode())
        assert request_body["itemData"]["Name"] == "test-queue"
        assert request_body["itemData"]["Reference"] == "test-ref-001"
        assert request_body["itemData"]["Priority"] == "High"
        assert request_body["itemData"]["SpecificContent"] == {"key": "value"}

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_item/{version}"
        )

    @pytest.mark.asyncio
    async def test_create_item_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "Reference": "test-ref-001",
                "Priority": "High",
                "SpecificContent": {"key": "value"},
            },
        )

        response = await service.create_item_async(
            queue_name="test-queue",
            reference="test-ref-001",
            specific_content={"key": "value"},
            priority="High",
        )

        # Access via model_extra since id and reference are not defined fields
        assert response.model_extra.get("Id") == 1
        assert response.name == "test-queue"
        assert response.model_extra.get("Reference") == "test-ref-001"
        assert response.priority == "High"
        assert response.specific_content == {"key": "value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem"
        )
        request_body = json.loads(sent_request.content.decode())
        assert request_body["itemData"]["Name"] == "test-queue"
        assert request_body["itemData"]["Reference"] == "test-ref-001"
        assert request_body["itemData"]["Priority"] == "High"
        assert request_body["itemData"]["SpecificContent"] == {"key": "value"}

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_item_async/{version}"
        )

    def test_create_items(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        queue_items = [
            QueueItem(
                name="test-queue",
                priority=QueueItemPriority.HIGH,
                specific_content={"key": "value"},
            ),
            QueueItem(
                name="test-queue",
                priority=QueueItemPriority.MEDIUM,
                specific_content={"key2": "value2"},
            ),
        ]
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.BulkAddQueueItems",
            status_code=200,
            json={
                "value": [
                    {
                        "Id": 1,
                        "Name": "test-queue",
                        "Priority": "High",
                        "SpecificContent": {"key": "value"},
                    },
                    {
                        "Id": 2,
                        "Name": "test-queue",
                        "Priority": "Medium",
                        "SpecificContent": {"key2": "value2"},
                    },
                ]
            },
        )

        response = service.create_items(
            queue_items, "test-queue", CommitType.ALL_OR_NOTHING
        )

        assert len(response["value"]) == 2
        assert response["value"][0]["Id"] == 1
        assert response["value"][0]["Name"] == "test-queue"
        assert response["value"][0]["Priority"] == "High"
        assert response["value"][0]["SpecificContent"] == {"key": "value"}
        assert response["value"][1]["Id"] == 2
        assert response["value"][1]["Name"] == "test-queue"
        assert response["value"][1]["Priority"] == "Medium"
        assert response["value"][1]["SpecificContent"] == {"key2": "value2"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.BulkAddQueueItems"
        )
        assert json.loads(sent_request.content.decode()) == {
            "queueName": "test-queue",
            "commitType": "AllOrNothing",
            "queueItems": [
                {
                    "Name": "test-queue",
                    "Priority": "High",
                    "SpecificContent": {"key": "value"},
                },
                {
                    "Name": "test-queue",
                    "Priority": "Medium",
                    "SpecificContent": {"key2": "value2"},
                },
            ],
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_items/{version}"
        )

    @pytest.mark.asyncio
    async def test_create_items_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        queue_items = [
            QueueItem(
                name="test-queue",
                priority=QueueItemPriority.HIGH,
                specific_content={"key": "value"},
            ),
            QueueItem(
                name="test-queue",
                priority=QueueItemPriority.MEDIUM,
                specific_content={"key2": "value2"},
            ),
        ]
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.BulkAddQueueItems",
            status_code=200,
            json={
                "value": [
                    {
                        "Id": 1,
                        "Name": "test-queue",
                        "Priority": "High",
                        "SpecificContent": {"key": "value"},
                    },
                    {
                        "Id": 2,
                        "Name": "test-queue",
                        "Priority": "Medium",
                        "SpecificContent": {"key2": "value2"},
                    },
                ]
            },
        )

        response = await service.create_items_async(
            queue_items, "test-queue", CommitType.ALL_OR_NOTHING
        )

        assert len(response["value"]) == 2
        assert response["value"][0]["Id"] == 1
        assert response["value"][0]["Name"] == "test-queue"
        assert response["value"][0]["Priority"] == "High"
        assert response["value"][0]["SpecificContent"] == {"key": "value"}
        assert response["value"][1]["Id"] == 2
        assert response["value"][1]["Name"] == "test-queue"
        assert response["value"][1]["Priority"] == "Medium"
        assert response["value"][1]["SpecificContent"] == {"key2": "value2"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.BulkAddQueueItems"
        )
        assert json.loads(sent_request.content.decode()) == {
            "queueName": "test-queue",
            "commitType": "AllOrNothing",
            "queueItems": [
                {
                    "Name": "test-queue",
                    "Priority": "High",
                    "SpecificContent": {"key": "value"},
                },
                {
                    "Name": "test-queue",
                    "Priority": "Medium",
                    "SpecificContent": {"key2": "value2"},
                },
            ],
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_items_async/{version}"
        )

    def test_create_transaction_item(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        transaction_item = TransactionItem(
            name="test-queue",
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "SpecificContent": {"key": "value"},
            },
        )

        response = service.create_transaction_item(transaction_item)

        assert response["Id"] == 1
        assert response["Name"] == "test-queue"
        assert response["SpecificContent"] == {"key": "value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction"
        )
        assert json.loads(sent_request.content.decode()) == {
            "transactionData": {
                "Name": "test-queue",
                "RobotIdentifier": "test-robot-key",
                "SpecificContent": {"key": "value"},
            }
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_transaction_item/{version}"
        )

    @pytest.mark.asyncio
    async def test_create_transaction_item_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        transaction_item = TransactionItem(
            name="test-queue",
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "SpecificContent": {"key": "value"},
            },
        )

        response = await service.create_transaction_item_async(transaction_item)

        assert response["Id"] == 1
        assert response["Name"] == "test-queue"
        assert response["SpecificContent"] == {"key": "value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction"
        )
        assert json.loads(sent_request.content.decode()) == {
            "transactionData": {
                "Name": "test-queue",
                "RobotIdentifier": "test-robot-key",
                "SpecificContent": {"key": "value"},
            }
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_transaction_item_async/{version}"
        )

    def test_update_progress_of_transaction_item(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        transaction_key = "test-transaction-key"
        progress = "Processing..."
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress",
            status_code=200,
            json={"status": "success"},
        )

        response = service.update_progress_of_transaction_item(
            transaction_key, progress
        )

        assert response["status"] == "success"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress"
        )
        assert json.loads(sent_request.content.decode()) == {"progress": progress}

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.update_progress_of_transaction_item/{version}"
        )

    @pytest.mark.asyncio
    async def test_update_progress_of_transaction_item_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        transaction_key = "test-transaction-key"
        progress = "Processing..."
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress",
            status_code=200,
            json={"status": "success"},
        )

        response = await service.update_progress_of_transaction_item_async(
            transaction_key, progress
        )

        assert response["status"] == "success"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress"
        )
        assert json.loads(sent_request.content.decode()) == {"progress": progress}

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.update_progress_of_transaction_item_async/{version}"
        )

    def test_complete_transaction_item(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        transaction_key = "test-transaction-key"
        result = TransactionItemResult(
            is_successful=True,
            output={"result": "success"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues({transaction_key})/UiPathODataSvc.SetTransactionResult",
            status_code=200,
            json={"status": "success"},
        )

        response = service.complete_transaction_item(transaction_key, result)

        assert response["status"] == "success"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues({transaction_key})/UiPathODataSvc.SetTransactionResult"
        )
        assert json.loads(sent_request.content.decode()) == {
            "transactionResult": {
                "IsSuccessful": True,
                "Output": {"result": "success"},
            }
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.complete_transaction_item/{version}"
        )

    @pytest.mark.asyncio
    async def test_complete_transaction_item_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        transaction_key = "test-transaction-key"
        result = TransactionItemResult(
            is_successful=True,
            output={"result": "success"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues({transaction_key})/UiPathODataSvc.SetTransactionResult",
            status_code=200,
            json={"status": "success"},
        )

        response = await service.complete_transaction_item_async(
            transaction_key, result
        )

        assert response["status"] == "success"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues({transaction_key})/UiPathODataSvc.SetTransactionResult"
        )
        assert json.loads(sent_request.content.decode()) == {
            "transactionResult": {
                "IsSuccessful": True,
                "Output": {"result": "success"},
            }
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.complete_transaction_item_async/{version}"
        )

    def test_create_item_requires_reference(self, service: QueuesService) -> None:
        """Test that create_item() requires the reference parameter."""
        with pytest.raises(TypeError, match="reference"):
            service.create_item(
                queue_name="test-queue", specific_content={"key": "value"}
            )

    def test_create_item_requires_specific_content(
        self, service: QueuesService
    ) -> None:
        """Test that create_item() requires the specific_content parameter."""
        with pytest.raises(TypeError, match="specific_content"):
            service.create_item(queue_name="test-queue", reference="REF-001")

    def test_create_item_requires_queue_selector(self, service: QueuesService) -> None:
        """Test that create_item() requires at least one of queue_name or queue_key."""
        with pytest.raises(
            ValueError, match="Either 'queue_name' or 'queue_key' must be provided"
        ):
            service.create_item(reference="REF-001", specific_content={"key": "value"})

    @pytest.mark.asyncio
    async def test_create_item_async_requires_reference(
        self, service: QueuesService
    ) -> None:
        """Test that create_item_async() requires the reference parameter."""
        with pytest.raises(TypeError, match="reference"):
            await service.create_item_async(
                queue_name="test-queue", specific_content={"key": "value"}
            )

    @pytest.mark.asyncio
    async def test_create_item_async_requires_queue_selector(
        self, service: QueuesService
    ) -> None:
        """Test that create_item_async() requires at least one of queue_name or queue_key."""
        with pytest.raises(
            ValueError, match="Either 'queue_name' or 'queue_key' must be provided"
        ):
            await service.create_item_async(
                reference="REF-001", specific_content={"key": "value"}
            )
