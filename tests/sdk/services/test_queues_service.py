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
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems",
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

        response = service.list_items()

        assert response["value"][0]["Id"] == 1
        assert response["value"][0]["Name"] == "test-queue"
        assert response["value"][0]["Priority"] == "High"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems"
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
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems",
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

        response = await service.list_items_async()

        assert response["value"][0]["Id"] == 1
        assert response["value"][0]["Name"] == "test-queue"
        assert response["value"][0]["Priority"] == "High"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems"
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
        queue_item = QueueItem(
            name="test-queue",
            priority=QueueItemPriority.HIGH,
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "Priority": "High",
                "SpecificContent": {"key": "value"},
            },
        )

        response = service.create_item(queue_item)

        assert response["Id"] == 1
        assert response["Name"] == "test-queue"
        assert response["Priority"] == "High"
        assert response["SpecificContent"] == {"key": "value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem"
        )
        assert json.loads(sent_request.content.decode()) == {
            "itemData": {
                "Name": "test-queue",
                "Priority": "High",
                "SpecificContent": {"key": "value"},
            }
        }

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
        queue_item = QueueItem(
            name="test-queue",
            priority=QueueItemPriority.HIGH,
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "Priority": "High",
                "SpecificContent": {"key": "value"},
            },
        )

        response = await service.create_item_async(queue_item)

        assert response["Id"] == 1
        assert response["Name"] == "test-queue"
        assert response["Priority"] == "High"
        assert response["SpecificContent"] == {"key": "value"}

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem"
        )
        assert json.loads(sent_request.content.decode()) == {
            "itemData": {
                "Name": "test-queue",
                "Priority": "High",
                "SpecificContent": {"key": "value"},
            }
        }

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
