import json
from datetime import datetime, timezone

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common.constants import (
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
    HEADER_USER_AGENT,
)
from uipath.platform.orchestrator import (
    CommitType,
    QueueItem,
    QueueItemPriority,
    Strategy,
    TransactionItem,
    TransactionItemResult,
)
from uipath.platform.orchestrator._queues_service import QueuesService


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
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

        response = service.create_item(queue_item, queue_name="test-queue")

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

        response = await service.create_item_async(queue_item, queue_name="test-queue")

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
                priority=QueueItemPriority.HIGH,
                specific_content={"key": "value"},
            ),
            QueueItem(
                priority=QueueItemPriority.LOW,
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
                        "Priority": "Low",
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
        assert response["value"][1]["Priority"] == "Low"
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
                    "Priority": "High",
                    "SpecificContent": {"key": "value"},
                },
                {
                    "Priority": "Low",
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
                priority=QueueItemPriority.HIGH,
                specific_content={"key": "value"},
            ),
            QueueItem(
                priority=QueueItemPriority.LOW,
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
                        "Priority": "Low",
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
        assert response["value"][1]["Priority"] == "Low"
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
                    "Priority": "High",
                    "SpecificContent": {"key": "value"},
                },
                {
                    "Priority": "Low",
                    "SpecificContent": {"key2": "value2"},
                },
            ],
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_items_async/{version}"
        )

    def test_create_item_with_reference(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        reference_value = "TEST-REF-12345"
        queue_item = QueueItem(
            reference=reference_value,
            priority=QueueItemPriority.HIGH,
            specific_content={"invoice_id": "INV-001"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "Reference": reference_value,
                "Priority": "High",
                "SpecificContent": {"invoice_id": "INV-001"},
            },
        )

        response = service.create_item(queue_item, queue_name="test-queue")

        assert response["Id"] == 1
        assert response["Name"] == "test-queue"
        assert response["Reference"] == reference_value
        assert response["Priority"] == "High"
        assert response["SpecificContent"] == {"invoice_id": "INV-001"}

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
                "Reference": reference_value,
                "Priority": "High",
                "SpecificContent": {"invoice_id": "INV-001"},
            }
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_item/{version}"
        )

    @pytest.mark.asyncio
    async def test_create_item_with_reference_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        reference_value = "TEST-REF-12345"
        queue_item = QueueItem(
            reference=reference_value,
            priority=QueueItemPriority.HIGH,
            specific_content={"invoice_id": "INV-001"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={
                "Id": 1,
                "Name": "test-queue",
                "Reference": reference_value,
                "Priority": "High",
                "SpecificContent": {"invoice_id": "INV-001"},
            },
        )

        response = await service.create_item_async(queue_item, queue_name="test-queue")

        assert response["Id"] == 1
        assert response["Name"] == "test-queue"
        assert response["Reference"] == reference_value
        assert response["Priority"] == "High"
        assert response["SpecificContent"] == {"invoice_id": "INV-001"}

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
                "Reference": reference_value,
                "Priority": "High",
                "SpecificContent": {"invoice_id": "INV-001"},
            }
        }

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.create_item_async/{version}"
        )

    def test_create_item_with_datetime_fields(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        defer = datetime(2026, 5, 1, 9, 0, 0, tzinfo=timezone.utc)
        due = datetime(2026, 5, 2, 17, 30, 0, tzinfo=timezone.utc)
        risk = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)
        queue_item = QueueItem(
            priority=QueueItemPriority.NORMAL,
            specific_content={"key": "value"},
            defer_date=defer,
            due_date=due,
            risk_sla_date=risk,
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={"Id": 1},
        )

        service.create_item(queue_item, queue_name="test-queue")

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        body = json.loads(sent_request.content.decode())
        assert body["itemData"]["DeferDate"] == defer.isoformat()
        assert body["itemData"]["DueDate"] == due.isoformat()
        assert body["itemData"]["RiskSlaDate"] == risk.isoformat()

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

        response = service.create_transaction_item(
            transaction_item, queue_name="test-queue"
        )

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

        response = await service.create_transaction_item_async(
            transaction_item, queue_name="test-queue"
        )

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

    def test_list_items_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems",
            status_code=200,
            json={"value": []},
        )

        service.list_items(folder_key="custom-folder-key")

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    def test_list_items_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems",
            status_code=200,
            json={"value": []},
        )

        service.list_items(folder_path="Custom/Folder/Path")

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_PATH in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_PATH] == "Custom/Folder/Path"

    @pytest.mark.asyncio
    async def test_list_items_async_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems",
            status_code=200,
            json={"value": []},
        )

        await service.list_items_async(folder_key="custom-folder-key")

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    def test_create_item_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        queue_item = QueueItem(
            priority=QueueItemPriority.HIGH,
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={"Id": 1},
        )

        service.create_item(
            queue_item, queue_name="test-queue", folder_key="custom-folder-key"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    def test_create_item_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        queue_item = QueueItem(
            priority=QueueItemPriority.HIGH,
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={"Id": 1},
        )

        service.create_item(
            queue_item, queue_name="test-queue", folder_path="Custom/Folder/Path"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_PATH in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_PATH] == "Custom/Folder/Path"

    @pytest.mark.asyncio
    async def test_create_item_async_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        queue_item = QueueItem(
            priority=QueueItemPriority.HIGH,
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem",
            status_code=200,
            json={"Id": 1},
        )

        await service.create_item_async(
            queue_item, queue_name="test-queue", folder_key="custom-folder-key"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    def test_create_items_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        queue_items = [
            QueueItem(
                priority=QueueItemPriority.HIGH,
                specific_content={"key": "value"},
            ),
        ]
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.BulkAddQueueItems",
            status_code=200,
            json={"value": []},
        )

        service.create_items(
            queue_items,
            "test-queue",
            CommitType.ALL_OR_NOTHING,
            folder_key="custom-folder-key",
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    @pytest.mark.asyncio
    async def test_create_items_async_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        queue_items = [
            QueueItem(
                priority=QueueItemPriority.HIGH,
                specific_content={"key": "value"},
            ),
        ]
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.BulkAddQueueItems",
            status_code=200,
            json={"value": []},
        )

        await service.create_items_async(
            queue_items,
            "test-queue",
            CommitType.ALL_OR_NOTHING,
            folder_path="Custom/Folder/Path",
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_PATH in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_PATH] == "Custom/Folder/Path"

    def test_create_transaction_item_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        transaction_item = TransactionItem(
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        service.create_transaction_item(
            transaction_item, queue_name="test-queue", folder_key="custom-folder-key"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    @pytest.mark.asyncio
    async def test_create_transaction_item_async_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        transaction_item = TransactionItem(
            specific_content={"key": "value"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        await service.create_transaction_item_async(
            transaction_item, queue_name="test-queue", folder_path="Custom/Folder/Path"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_PATH in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_PATH] == "Custom/Folder/Path"

    def test_update_progress_of_transaction_item_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        transaction_key = "test-transaction-key"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress",
            status_code=200,
            json={"status": "success"},
        )

        service.update_progress_of_transaction_item(
            transaction_key, "Processing...", folder_key="custom-folder-key"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    @pytest.mark.asyncio
    async def test_update_progress_of_transaction_item_async_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        transaction_key = "test-transaction-key"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress",
            status_code=200,
            json={"status": "success"},
        )

        await service.update_progress_of_transaction_item_async(
            transaction_key, "Processing...", folder_path="Custom/Folder/Path"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_PATH in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_PATH] == "Custom/Folder/Path"

    def test_complete_transaction_item_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
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

        service.complete_transaction_item(
            transaction_key, result, folder_key="custom-folder-key"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_KEY in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    @pytest.mark.asyncio
    async def test_complete_transaction_item_async_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
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

        await service.complete_transaction_item_async(
            transaction_key, result, folder_path="Custom/Folder/Path"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert HEADER_FOLDER_PATH in sent_request.headers
        assert sent_request.headers[HEADER_FOLDER_PATH] == "Custom/Folder/Path"

    def test_start_transaction_item_picks_next_available(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 42, "Key": "abc-123", "Status": "InProgress"},
        )

        response = service.start_transaction_item(queue_name="test-queue")

        assert response["Id"] == 42
        assert response["Status"] == "InProgress"

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.method == "POST"
        body = json.loads(sent_request.content.decode())
        assert body == {
            "transactionData": {
                "Name": "test-queue",
                "RobotIdentifier": "test-robot-key",
            }
        }
        assert "SpecificContent" not in body["transactionData"]
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.start_transaction_item/{version}"
        )

    def test_start_transaction_item_with_reference_equals(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        service.start_transaction_item(
            queue_name="test-queue",
            reference="ABC-123",
            reference_filter_option=Strategy.EQUALS,
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        body = json.loads(sent_request.content.decode())
        assert body == {
            "transactionData": {
                "Name": "test-queue",
                "RobotIdentifier": "test-robot-key",
                "Reference": "ABC-123",
                "ReferenceFilterOption": "Equals",
            }
        }

    def test_start_transaction_item_with_reference_starts_with(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        service.start_transaction_item(
            queue_name="test-queue",
            reference="ABC-",
            reference_filter_option=Strategy.STARTS_WITH,
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        body = json.loads(sent_request.content.decode())
        assert body["transactionData"]["Reference"] == "ABC-"
        assert body["transactionData"]["ReferenceFilterOption"] == "StartsWith"

    def test_start_transaction_item_omits_robot_when_env_unset(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.delenv("UIPATH_ROBOT_KEY", raising=False)
        monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
        local_service = QueuesService(
            config=config, execution_context=UiPathExecutionContext()
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        local_service.start_transaction_item(queue_name="test-queue")

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        body = json.loads(sent_request.content.decode())
        assert body == {"transactionData": {"Name": "test-queue"}}
        assert "RobotIdentifier" not in body["transactionData"]

    def test_start_transaction_item_with_dates_and_parent_operation_id(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        defer = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        due = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)
        service.start_transaction_item(
            queue_name="test-queue",
            defer_date=defer,
            due_date=due,
            parent_operation_id="op-123",
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        body = json.loads(sent_request.content.decode())
        assert body["transactionData"]["DeferDate"] == defer.isoformat()
        assert body["transactionData"]["DueDate"] == due.isoformat()
        assert body["transactionData"]["ParentOperationId"] == "op-123"

    def test_start_transaction_item_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        service.start_transaction_item(
            queue_name="test-queue", folder_key="custom-folder-key"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.headers[HEADER_FOLDER_KEY] == "custom-folder-key"

    @pytest.mark.asyncio
    async def test_start_transaction_item_async(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 7, "Status": "InProgress"},
        )

        response = await service.start_transaction_item_async(
            queue_name="test-queue",
            reference="REF-1",
            reference_filter_option=Strategy.EQUALS,
        )

        assert response["Id"] == 7
        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        body = json.loads(sent_request.content.decode())
        assert body["transactionData"]["Reference"] == "REF-1"
        assert body["transactionData"]["ReferenceFilterOption"] == "Equals"
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.QueuesService.start_transaction_item_async/{version}"
        )

    @pytest.mark.asyncio
    async def test_start_transaction_item_async_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: QueuesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction",
            status_code=200,
            json={"Id": 1},
        )

        await service.start_transaction_item_async(
            queue_name="test-queue", folder_path="Custom/Folder/Path"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.headers[HEADER_FOLDER_PATH] == "Custom/Folder/Path"
