from typing import Any, Dict, List, Union

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import CommitType, QueueItem, TransactionItem, TransactionItemResult
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class QueuesService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def list_items(self) -> Response:
        """
        List all queue items.

        Returns:
            A Response object.
        """
        spec = self._list_items_spec()
        return self.request(spec.method, url=spec.endpoint)

    async def list_items_async(self) -> Response:
        """
        List all queue items.

        Returns:
            A Response object.
        """

        spec = self._list_items_spec()
        return await self.request_async(spec.method, url=spec.endpoint)

    def create_item(self, item: Union[Dict[str, Any], QueueItem]) -> Response:
        """
        Create a new queue item.

        Args:
            item: A dictionary that contains the queue item data or a QueueItem object.

        Returns:
            A Response object.
        """

        spec = self._create_item_spec(item)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_item_async(
        self, item: Union[Dict[str, Any], QueueItem]
    ) -> Response:
        """
        Create a new queue item.

        Args:
            item: A dictionary that contains the queue item data or a QueueItem object.

        Returns:
            A Response object.
        """

        spec = self._create_item_spec(item)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def create_items(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
    ) -> Response:
        """
        Create multiple queue items.

        Args:
            items: A list of dictionaries that contain the queue item data or a QueueItem object.
            queue_name: The name of the queue.
            commit_type: AllOrNothing | StopOnFirstFailure | ProcessAllIndependently

        Returns:
            A Response object.
        """

        spec = self._create_items_spec(items, queue_name, commit_type)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_items_async(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
    ) -> Response:
        """
        Create multiple queue items.

        Args:
            items: A list of dictionaries that contain the queue item data or a QueueItem object.
            queue_name: The name of the queue.
            commit_type: AllOrNothing | StopOnFirstFailure | ProcessAllIndependently

        Returns:
            A Response object.
        """

        spec = self._create_items_spec(items, queue_name, commit_type)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def create_transaction_item(
        self, item: Union[Dict[str, Any], TransactionItem], no_robot: bool = False
    ) -> Response:
        """
        Create or update a queue item. If the item already exists, it will be updated.
        Otherwise, it will be created and started (status: InProgress)

        Args:
            item: A dictionary that contains the transaction item data or a TransactionItem object.

        Returns:
            A Response object.
        """

        spec = self._create_transaction_item_spec(item, no_robot)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_transaction_item_async(
        self, item: Union[Dict[str, Any], TransactionItem], no_robot: bool = False
    ) -> Response:
        """
        Create or update a queue item. If the item already exists, it will be updated.
        Otherwise, it will be created and started (status: InProgress)

        Args:
            item: A dictionary that contains the transaction item data or a TransactionItem object.

        Returns:
            A Response object.
        """

        spec = self._create_transaction_item_spec(item, no_robot)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def update_progress_of_transaction_item(
        self, transaction_key: str, progress: str
    ) -> Response:
        """
        Update the progress of a transaction item that is currently being processed.

        Args:
            transaction_key: The key of the transaction item.
            progress: The progress of the transaction item.

        Returns:
            A Response object.
        """

        spec = self._update_progress_of_transaction_item_spec(transaction_key, progress)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def update_progress_of_transaction_item_async(
        self, transaction_key: str, progress: str
    ) -> Response:
        """
        Update the progress of a transaction item that is currently being processed.

        Args:
            transaction_key: The key of the transaction item.
            progress: The progress of the transaction item.

        Returns:
            A Response object.
        """

        spec = self._update_progress_of_transaction_item_spec(transaction_key, progress)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def complete_transaction_item(
        self, transaction_key: str, result: Union[Dict[str, Any], TransactionItemResult]
    ) -> Response:
        """
        Complete the processing of a transaction item.
        """

        spec = self._complete_transaction_item_spec(transaction_key, result)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def complete_transaction_item_async(
        self, transaction_key: str, result: Union[Dict[str, Any], TransactionItemResult]
    ) -> Response:
        """
        Complete the processing of a transaction item.
        """

        spec = self._complete_transaction_item_spec(transaction_key, result)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _list_items_spec(self) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                "/orchestrator_/odata/Queues/UiPathODataSvc.GetQueueItems"
            ),
        )

    def _create_item_spec(self, item: Union[Dict[str, Any], QueueItem]) -> RequestSpec:
        if isinstance(item, dict):
            queue_item = QueueItem(**item)
        elif isinstance(item, QueueItem):
            queue_item = item

        json_payload = {
            "itemData": queue_item.model_dump(exclude_unset=True, by_alias=True)
        }

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Queues/UiPathODataSvc.AddQueueItem"
            ),
            json=json_payload,
        )

    def _create_items_spec(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Queues/UiPathODataSvc.BulkAddQueueItems"
            ),
            json={
                "queueName": queue_name,
                "commitType": commit_type.value,
                "queueItems": [
                    item.model_dump(exclude_unset=True, by_alias=True)
                    if isinstance(item, QueueItem)
                    else QueueItem(**item).model_dump(exclude_unset=True, by_alias=True)
                    for item in items
                ],
            },
        )

    def _create_transaction_item_spec(
        self, item: Union[Dict[str, Any], TransactionItem], no_robot: bool = False
    ) -> RequestSpec:
        if isinstance(item, dict):
            transaction_item = TransactionItem(**item)
        elif isinstance(item, TransactionItem):
            transaction_item = item

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Queues/UiPathODataSvc.StartTransaction"
            ),
            json={
                "transactionData": {
                    **transaction_item.model_dump(exclude_unset=True, by_alias=True),
                    **(
                        {"RobotIdentifier": self._execution_context.robot_key}
                        if not no_robot
                        else {}
                    ),
                }
            },
        )

    def _update_progress_of_transaction_item_spec(
        self, transaction_key: str, progress: str
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress"
            ),
            json={"progress": progress},
        )

    def _complete_transaction_item_spec(
        self, transaction_key: str, result: Union[Dict[str, Any], TransactionItemResult]
    ) -> RequestSpec:
        if isinstance(result, dict):
            transaction_result = TransactionItemResult(**result)
        elif isinstance(result, TransactionItemResult):
            transaction_result = result

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Queues({transaction_key})/UiPathODataSvc.SetTransactionResult"
            ),
            json={
                "transactionResult": transaction_result.model_dump(
                    exclude_unset=True, by_alias=True
                )
            },
        )
