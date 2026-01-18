from typing import Any, Dict, List, Optional, Union

from httpx import Response

from ..._utils import Endpoint, RequestSpec, header_folder
from ...tracing import traced
from ..common import BaseService, FolderContext, UiPathApiConfig, UiPathExecutionContext
from .queues import (
    CommitType,
    QueueItem,
    TransactionItem,
    TransactionItemResult,
)


class QueuesService(FolderContext, BaseService):
    """Service for managing UiPath queues and queue items.

    Queues are a fundamental component of UiPath automation that enable distributed
    and scalable processing of work items.
    """

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="queues_list_items", run_type="uipath")
    def list_items(
        self,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Retrieves a list of queue items from the Orchestrator.

        Args:
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the list of queue items.
        """
        spec = self._list_items_spec(folder_key=folder_key, folder_path=folder_path)
        response = self.request(spec.method, url=spec.endpoint, headers=spec.headers)

        return response.json()

    @traced(name="queues_list_items", run_type="uipath")
    async def list_items_async(
        self,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Asynchronously retrieves a list of queue items from the Orchestrator.

        Args:
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the list of queue items.
        """
        spec = self._list_items_spec(folder_key=folder_key, folder_path=folder_path)
        response = await self.request_async(
            spec.method, url=spec.endpoint, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_create_item", run_type="uipath")
    def create_item(
        self,
        item: Union[Dict[str, Any], QueueItem],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Creates a new queue item in the Orchestrator.

        Args:
            item: Queue item data, either as a dictionary or QueueItem instance.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the created queue item details.

        Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)
        """
        spec = self._create_item_spec(
            item, folder_key=folder_key, folder_path=folder_path
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_create_item", run_type="uipath")
    async def create_item_async(
        self,
        item: Union[Dict[str, Any], QueueItem],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Asynchronously creates a new queue item in the Orchestrator.

        Args:
            item: Queue item data, either as a dictionary or QueueItem instance.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the created queue item details.

        Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)
        """
        spec = self._create_item_spec(
            item, folder_key=folder_key, folder_path=folder_path
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_create_items", run_type="uipath")
    def create_items(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Creates multiple queue items in bulk.

        Args:
            items: List of queue items to create, each either a dictionary or QueueItem instance.
            queue_name: Name of the target queue.
            commit_type: Type of commit operation to use for the bulk operation.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the bulk operation result.
        """
        spec = self._create_items_spec(
            items,
            queue_name,
            commit_type,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_create_items", run_type="uipath")
    async def create_items_async(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Asynchronously creates multiple queue items in bulk.

        Args:
            items: List of queue items to create, each either a dictionary or QueueItem instance.
            queue_name: Name of the target queue.
            commit_type: Type of commit operation to use for the bulk operation.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the bulk operation result.
        """
        spec = self._create_items_spec(
            items,
            queue_name,
            commit_type,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_create_transaction_item", run_type="uipath")
    def create_transaction_item(
        self,
        item: Union[Dict[str, Any], TransactionItem],
        no_robot: bool = False,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Creates a new transaction item in a queue.

        Args:
            item: Transaction item data, either as a dictionary or TransactionItem instance.
            no_robot: If True, the transaction will not be associated with a robot. Defaults to False.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the transaction item details.
        """
        spec = self._create_transaction_item_spec(
            item, no_robot, folder_key=folder_key, folder_path=folder_path
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_create_transaction_item", run_type="uipath")
    async def create_transaction_item_async(
        self,
        item: Union[Dict[str, Any], TransactionItem],
        no_robot: bool = False,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Asynchronously creates a new transaction item in a queue.

        Args:
            item: Transaction item data, either as a dictionary or TransactionItem instance.
            no_robot: If True, the transaction will not be associated with a robot. Defaults to False.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response containing the transaction item details.
        """
        spec = self._create_transaction_item_spec(
            item, no_robot, folder_key=folder_key, folder_path=folder_path
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_update_progress_of_transaction_item", run_type="uipath")
    def update_progress_of_transaction_item(
        self,
        transaction_key: str,
        progress: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Updates the progress of a transaction item.

        Args:
            transaction_key: Unique identifier of the transaction.
            progress: Progress message to set.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response confirming the progress update.

        Related Activity: [Set Transaction Progress](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-progress)
        """
        spec = self._update_progress_of_transaction_item_spec(
            transaction_key, progress, folder_key=folder_key, folder_path=folder_path
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_update_progress_of_transaction_item", run_type="uipath")
    async def update_progress_of_transaction_item_async(
        self,
        transaction_key: str,
        progress: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Asynchronously updates the progress of a transaction item.

        Args:
            transaction_key: Unique identifier of the transaction.
            progress: Progress message to set.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response confirming the progress update.

        Related Activity: [Set Transaction Progress](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-progress)
        """
        spec = self._update_progress_of_transaction_item_spec(
            transaction_key, progress, folder_key=folder_key, folder_path=folder_path
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_complete_transaction_item", run_type="uipath")
    def complete_transaction_item(
        self,
        transaction_key: str,
        result: Union[Dict[str, Any], TransactionItemResult],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Completes a transaction item with the specified result.

        Args:
            transaction_key: Unique identifier of the transaction to complete.
            result: Result data for the transaction, either as a dictionary or TransactionItemResult instance.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response confirming the transaction completion.

        Related Activity: [Set Transaction Status](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-status)
        """
        spec = self._complete_transaction_item_spec(
            transaction_key, result, folder_key=folder_key, folder_path=folder_path
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @traced(name="queues_complete_transaction_item", run_type="uipath")
    async def complete_transaction_item_async(
        self,
        transaction_key: str,
        result: Union[Dict[str, Any], TransactionItemResult],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Asynchronously completes a transaction item with the specified result.

        Args:
            transaction_key: Unique identifier of the transaction to complete.
            result: Result data for the transaction, either as a dictionary or TransactionItemResult instance.
            folder_key (Optional[str]): The key of the folder. Overrides the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Overrides the default one set in the SDK config.

        Returns:
            Response: HTTP response confirming the transaction completion.

        Related Activity: [Set Transaction Status](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-status)
        """
        spec = self._complete_transaction_item_spec(
            transaction_key, result, folder_key=folder_key, folder_path=folder_path
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return response.json()

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _list_items_spec(
        self,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/QueueItems"),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _create_item_spec(
        self,
        item: Union[Dict[str, Any], QueueItem],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
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
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _create_items_spec(
        self,
        items: List[Union[Dict[str, Any], QueueItem]],
        queue_name: str,
        commit_type: CommitType,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
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
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _create_transaction_item_spec(
        self,
        item: Union[Dict[str, Any], TransactionItem],
        no_robot: bool = False,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
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
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _update_progress_of_transaction_item_spec(
        self,
        transaction_key: str,
        progress: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"/orchestrator_/odata/QueueItems({transaction_key})/UiPathODataSvc.SetTransactionProgress"
            ),
            json={"progress": progress},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _complete_transaction_item_spec(
        self,
        transaction_key: str,
        result: Union[Dict[str, Any], TransactionItemResult],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
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
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
