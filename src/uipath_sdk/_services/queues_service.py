from typing import Any, Dict, List, Union

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import CommitType, QueueItem, TransactionItem, TransactionItemResult
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class QueuesService(FolderContext, BaseService):
    """Service for managing UiPath queues and queue items.

    Queues are a fundamental component of UiPath automation that enable distributed
    and scalable processing of work items.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def list_items(self) -> Response:
        """Retrieves a list of queue items from the Orchestrator.

        Returns:
            Response: HTTP response containing the list of queue items.
        """
        spec = self._list_items_spec()
        return self.request(spec.method, url=spec.endpoint)

    async def list_items_async(self) -> Response:
        """Asynchronously retrieves a list of queue items from the Orchestrator.

        Returns:
            Response: HTTP response containing the list of queue items.
        """
        spec = self._list_items_spec()
        return await self.request_async(spec.method, url=spec.endpoint)

    def create_item(self, item: Union[Dict[str, Any], QueueItem]) -> Response:
        """Creates a new queue item in the Orchestrator.

        Args:
            item: Queue item data, either as a dictionary or QueueItem instance.

        Returns:
            Response: HTTP response containing the created queue item details.

        Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)
        """
        spec = self._create_item_spec(item)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_item_async(
        self, item: Union[Dict[str, Any], QueueItem]
    ) -> Response:
        """Asynchronously creates a new queue item in the Orchestrator.

        Args:
            item: Queue item data, either as a dictionary or QueueItem instance.

        Returns:
            Response: HTTP response containing the created queue item details.

        Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)
        """
        spec = self._create_item_spec(item)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def create_items(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
    ) -> Response:
        """Creates multiple queue items in bulk.

        Args:
            items: List of queue items to create, each either a dictionary or QueueItem instance.
            queue_name: Name of the target queue.
            commit_type: Type of commit operation to use for the bulk operation.

        Returns:
            Response: HTTP response containing the bulk operation result.
        """
        spec = self._create_items_spec(items, queue_name, commit_type)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_items_async(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
    ) -> Response:
        """Asynchronously creates multiple queue items in bulk.

        Args:
            items: List of queue items to create, each either a dictionary or QueueItem instance.
            queue_name: Name of the target queue.
            commit_type: Type of commit operation to use for the bulk operation.

        Returns:
            Response: HTTP response containing the bulk operation result.
        """
        spec = self._create_items_spec(items, queue_name, commit_type)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def create_transaction_item(
        self, item: Union[Dict[str, Any], TransactionItem], no_robot: bool = False
    ) -> Response:
        """Creates a new transaction item in a queue.

        Args:
            item: Transaction item data, either as a dictionary or TransactionItem instance.
            no_robot: If True, the transaction will not be associated with a robot. Defaults to False.

        Returns:
            Response: HTTP response containing the transaction item details.
        """
        spec = self._create_transaction_item_spec(item, no_robot)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_transaction_item_async(
        self, item: Union[Dict[str, Any], TransactionItem], no_robot: bool = False
    ) -> Response:
        """Asynchronously creates a new transaction item in a queue.

        Args:
            item: Transaction item data, either as a dictionary or TransactionItem instance.
            no_robot: If True, the transaction will not be associated with a robot. Defaults to False.

        Returns:
            Response: HTTP response containing the transaction item details.
        """
        spec = self._create_transaction_item_spec(item, no_robot)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def update_progress_of_transaction_item(
        self, transaction_key: str, progress: str
    ) -> Response:
        """Updates the progress of a transaction item.

        Args:
            transaction_key: Unique identifier of the transaction.
            progress: Progress message to set.

        Returns:
            Response: HTTP response confirming the progress update.

        Related Activity: [Set Transaction Progress](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-progress)
        """
        spec = self._update_progress_of_transaction_item_spec(transaction_key, progress)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def update_progress_of_transaction_item_async(
        self, transaction_key: str, progress: str
    ) -> Response:
        """Asynchronously updates the progress of a transaction item.

        Args:
            transaction_key: Unique identifier of the transaction.
            progress: Progress message to set.

        Returns:
            Response: HTTP response confirming the progress update.

        Related Activity: [Set Transaction Progress](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-progress)
        """
        spec = self._update_progress_of_transaction_item_spec(transaction_key, progress)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def complete_transaction_item(
        self, transaction_key: str, result: Union[Dict[str, Any], TransactionItemResult]
    ) -> Response:
        """Completes a transaction item with the specified result.

        Args:
            transaction_key: Unique identifier of the transaction to complete.
            result: Result data for the transaction, either as a dictionary or TransactionItemResult instance.

        Returns:
            Response: HTTP response confirming the transaction completion.

        Related Activity: [Set Transaction Status](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-status)
        """
        spec = self._complete_transaction_item_spec(transaction_key, result)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def complete_transaction_item_async(
        self, transaction_key: str, result: Union[Dict[str, Any], TransactionItemResult]
    ) -> Response:
        """Asynchronously completes a transaction item with the specified result.

        Args:
            transaction_key: Unique identifier of the transaction to complete.
            result: Result data for the transaction, either as a dictionary or TransactionItemResult instance.

        Returns:
            Response: HTTP response confirming the transaction completion.

        Related Activity: [Set Transaction Status](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-status)
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
