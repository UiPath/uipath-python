from typing import Any, Dict, List, Union

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import CommitType, QueueItem, TransactionItem, TransactionItemResult
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class QueuesService(FolderContext, BaseService):
    """
    Service for managing UiPath queues and queue items.

    Queues are a fundamental component of UiPath automation that enable distributed
    and scalable processing of work items. This service provides methods to:
    - List and create queue items
    - Handle transaction-based processing of items
    - Manage item progress and completion
    - Support bulk operations

    The service supports both synchronous and asynchronous operations and provides
    flexible input formats (dictionaries or model objects) for queue items.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        """
        Initialize the queues service.

        Args:
            config (Config): Configuration object containing API settings.
            execution_context (ExecutionContext): Context object containing execution-specific
                information.
        """
        super().__init__(config=config, execution_context=execution_context)

    def list_items(self) -> Response:
        """
        List all queue items in the current folder.

        This method retrieves all queue items that are accessible within the current
        folder context, including their status, priority, and other metadata.

        Returns:
            Response: The HTTP response containing a list of queue items.

        Example:
            ```python
            # Get all queue items
            response = queues_service.list_items()
            items = response.json()
            for item in items["value"]:
                print(f"Item {item['Id']}: {item['Status']}")
            ```
        """
        spec = self._list_items_spec()
        return self.request(spec.method, url=spec.endpoint)

    async def list_items_async(self) -> Response:
        """
        Asynchronously list all queue items in the current folder.

        This method retrieves all queue items that are accessible within the current
        folder context, including their status, priority, and other metadata.

        Returns:
            Response: The HTTP response containing a list of queue items.
        """
        spec = self._list_items_spec()
        return await self.request_async(spec.method, url=spec.endpoint)

    def create_item(self, item: Union[Dict[str, Any], QueueItem]) -> Response:
        """
        Create a new queue item.

        This method adds a new item to a queue for processing. The item can be
        specified either as a dictionary or as a QueueItem object.

        Args:
            item (Union[Dict[str, Any], QueueItem]): The item to add to the queue.
                Can be either a dictionary with item properties or a QueueItem instance.

        Returns:
            Response: The HTTP response containing the created item details.

        Example:
            ```python
            # Create an item using a dictionary
            response = queues_service.create_item({
                "Name": "Process Invoice",
                "Priority": "High",
                "SpecificContent": {"InvoiceId": "INV-123"}
            })

            # Or using a QueueItem object
            item = QueueItem(
                Name="Process Invoice",
                Priority="High",
                SpecificContent={"InvoiceId": "INV-123"}
            )
            response = queues_service.create_item(item)
            ```
        """
        spec = self._create_item_spec(item)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_item_async(
        self, item: Union[Dict[str, Any], QueueItem]
    ) -> Response:
        """
        Asynchronously create a new queue item.

        This method adds a new item to a queue for processing. The item can be
        specified either as a dictionary or as a QueueItem object.

        Args:
            item (Union[Dict[str, Any], QueueItem]): The item to add to the queue.
                Can be either a dictionary with item properties or a QueueItem instance.

        Returns:
            Response: The HTTP response containing the created item details.
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
        Create multiple queue items in a single operation.

        This method provides efficient bulk creation of queue items with configurable
        commit behavior to handle failures.

        Args:
            items (List[Union[Dict[str, Any], QueueItem]]): List of items to add.
                Each item can be either a dictionary or a QueueItem instance.
            queue_name (str): The name of the queue to add items to.
            commit_type (CommitType): How to handle failures during bulk creation:
                - AllOrNothing: Either all items are created or none
                - StopOnFirstFailure: Stop processing after first failure
                - ProcessAllIndependently: Try to create all items regardless of failures

        Returns:
            Response: The HTTP response containing results of the bulk operation.

        Example:
            ```python
            # Create multiple items with all-or-nothing behavior
            items = [
                {"Name": "Invoice 1", "SpecificContent": {"Id": "INV-1"}},
                {"Name": "Invoice 2", "SpecificContent": {"Id": "INV-2"}}
            ]
            response = queues_service.create_items(
                items,
                queue_name="invoices",
                commit_type=CommitType.ALL_OR_NOTHING
            )
            ```
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
        Asynchronously create multiple queue items in a single operation.

        This method provides efficient bulk creation of queue items with configurable
        commit behavior to handle failures.

        Args:
            items (List[Union[Dict[str, Any], QueueItem]]): List of items to add.
                Each item can be either a dictionary or a QueueItem instance.
            queue_name (str): The name of the queue to add items to.
            commit_type (CommitType): How to handle failures during bulk creation:
                - AllOrNothing: Either all items are created or none
                - StopOnFirstFailure: Stop processing after first failure
                - ProcessAllIndependently: Try to create all items regardless of failures

        Returns:
            Response: The HTTP response containing results of the bulk operation.
        """
        spec = self._create_items_spec(items, queue_name, commit_type)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def create_transaction_item(
        self, item: Union[Dict[str, Any], TransactionItem], no_robot: bool = False
    ) -> Response:
        """
        Create or update a transaction item in a queue.

        Transaction items represent work that is actively being processed. This method
        either creates a new transaction or updates an existing one, setting its
        status to InProgress.

        Args:
            item (Union[Dict[str, Any], TransactionItem]): The transaction item to
                create or update. Can be either a dictionary or a TransactionItem instance.
            no_robot (bool, optional): If True, creates the transaction without
                associating it with a robot. Defaults to False.

        Returns:
            Response: The HTTP response containing the transaction details.

        Example:
            ```python
            # Create a transaction for processing an invoice
            response = queues_service.create_transaction_item({
                "QueueName": "invoices",
                "Reference": "INV-123",
                "Priority": "High"
            })
            ```
        """
        spec = self._create_transaction_item_spec(item, no_robot)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def create_transaction_item_async(
        self, item: Union[Dict[str, Any], TransactionItem], no_robot: bool = False
    ) -> Response:
        """
        Asynchronously create or update a transaction item in a queue.

        Transaction items represent work that is actively being processed. This method
        either creates a new transaction or updates an existing one, setting its
        status to InProgress.

        Args:
            item (Union[Dict[str, Any], TransactionItem]): The transaction item to
                create or update. Can be either a dictionary or a TransactionItem instance.
            no_robot (bool, optional): If True, creates the transaction without
                associating it with a robot. Defaults to False.

        Returns:
            Response: The HTTP response containing the transaction details.
        """
        spec = self._create_transaction_item_spec(item, no_robot)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def update_progress_of_transaction_item(
        self, transaction_key: str, progress: str
    ) -> Response:
        """
        Update the progress of an in-process transaction item.

        This method allows reporting intermediate progress while processing a
        transaction item, which can be useful for monitoring long-running operations.

        Args:
            transaction_key (str): The unique identifier of the transaction.
            progress (str): A description of the current progress state.

        Returns:
            Response: The HTTP response confirming the progress update.

        Example:
            ```python
            # Update progress of a transaction
            queues_service.update_progress_of_transaction_item(
                "tx-123-abc",
                "Processing page 3 of 10"
            )
            ```
        """
        spec = self._update_progress_of_transaction_item_spec(transaction_key, progress)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def update_progress_of_transaction_item_async(
        self, transaction_key: str, progress: str
    ) -> Response:
        """
        Asynchronously update the progress of an in-process transaction item.

        This method allows reporting intermediate progress while processing a
        transaction item, which can be useful for monitoring long-running operations.

        Args:
            transaction_key (str): The unique identifier of the transaction.
            progress (str): A description of the current progress state.

        Returns:
            Response: The HTTP response confirming the progress update.
        """
        spec = self._update_progress_of_transaction_item_spec(transaction_key, progress)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    def complete_transaction_item(
        self, transaction_key: str, result: Union[Dict[str, Any], TransactionItemResult]
    ) -> Response:
        """
        Mark a transaction item as completed.

        This method finalizes the processing of a transaction item, recording its
        final status and any result data.

        Args:
            transaction_key (str): The unique identifier of the transaction.
            result (Union[Dict[str, Any], TransactionItemResult]): The result of
                processing. Can be either a dictionary or a TransactionItemResult instance.

        Returns:
            Response: The HTTP response confirming the completion.

        Example:
            ```python
            # Complete a transaction with success
            queues_service.complete_transaction_item(
                "tx-123-abc",
                {
                    "IsSuccessful": True,
                    "Output": {"ProcessedInvoiceId": "INV-123"}
                }
            )
            ```
        """
        spec = self._complete_transaction_item_spec(transaction_key, result)
        return self.request(spec.method, url=spec.endpoint, json=spec.json)

    async def complete_transaction_item_async(
        self, transaction_key: str, result: Union[Dict[str, Any], TransactionItemResult]
    ) -> Response:
        """
        Asynchronously mark a transaction item as completed.

        This method finalizes the processing of a transaction item, recording its
        final status and any result data.

        Args:
            transaction_key (str): The unique identifier of the transaction.
            result (Union[Dict[str, Any], TransactionItemResult]): The result of
                processing. Can be either a dictionary or a TransactionItemResult instance.

        Returns:
            Response: The HTTP response confirming the completion.
        """
        spec = self._complete_transaction_item_spec(transaction_key, result)
        return await self.request_async(spec.method, url=spec.endpoint, json=spec.json)

    @property
    def custom_headers(self) -> Dict[str, str]:
        """
        Get custom headers for queue-related requests.

        Returns:
            Dict[str, str]: Headers containing folder context information.
        """
        return self.folder_headers

    def _list_items_spec(self) -> RequestSpec:
        """
        Create a request specification for listing queue items.

        Returns:
            RequestSpec: The request specification for the API call.
        """
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                "/orchestrator_/odata/Queues/UiPathODataSvc.GetQueueItems"
            ),
        )

    def _create_item_spec(self, item: Union[Dict[str, Any], QueueItem]) -> RequestSpec:
        """
        Create a request specification for creating a queue item.

        Args:
            item (Union[Dict[str, Any], QueueItem]): The item to create.

        Returns:
            RequestSpec: The request specification for the API call.
        """
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
        """
        Create a request specification for bulk creation of queue items.

        Args:
            items (List[Union[Dict[str, Any], QueueItem]]): The items to create.
            queue_name (str): The name of the target queue.
            commit_type (CommitType): The commit behavior to use.

        Returns:
            RequestSpec: The request specification for the API call.
        """
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
