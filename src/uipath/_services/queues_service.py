from datetime import datetime
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, resource_override
from ..models import (
    CommitType,
    QueueDefinition,
    QueueItem,
    TransactionItem,
    TransactionItemResult,
)
from ..models.errors import PaginationLimitError
from ..tracing._traced import traced
from ._base_service import BaseService


class QueuesService(FolderContext, BaseService):
    """Service for managing UiPath queues and queue items.

    Queues are a fundamental component of UiPath automation that enable distributed
    and scalable processing of work items.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="queues_list_definitions", run_type="uipath")
    def list_definitions(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> Iterator[QueueDefinition]:
        """List queue definitions with auto-pagination.

        Args:
            folder_path: Folder path to filter queues
            folder_key: Folder key (mutually exclusive with folder_path)
            name: Filter by queue name (contains match)
            filter: OData $filter expression
            orderby: OData $orderby expression
            top: Maximum items per page (default 100)
            skip: Number of items to skip

        Yields:
            QueueDefinition: Queue definition instances

        Examples:
            >>> for queue in sdk.queues.list_definitions():
            ...     print(queue.name, queue.max_number_of_retries)
        """
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_definitions_spec(
                folder_path=folder_path,
                folder_key=folder_key,
                name=name,
                filter=filter,
                orderby=orderby,
                skip=current_skip,
                top=top,
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                queue_def = QueueDefinition.model_validate(item)
                yield queue_def

            pages_fetched += 1

            if len(items) < top:
                break

            current_skip += top

        else:
            if items and len(items) == top:
                raise PaginationLimitError.create(
                    max_pages=MAX_PAGES,
                    items_per_page=top,
                    method_name="list_definitions",
                    current_skip=current_skip,
                    filter_example="Name eq 'MyQueue'",
                )

    @traced(name="queues_list_definitions", run_type="uipath")
    async def list_definitions_async(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> AsyncIterator[QueueDefinition]:
        """Async version of list_definitions()."""
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_definitions_spec(
                folder_path=folder_path,
                folder_key=folder_key,
                name=name,
                filter=filter,
                orderby=orderby,
                skip=current_skip,
                top=top,
            )
            response = (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                )
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                queue_def = QueueDefinition.model_validate(item)
                yield queue_def

            pages_fetched += 1

            if len(items) < top:
                break

            current_skip += top

        else:
            if items and len(items) == top:
                raise PaginationLimitError.create(
                    max_pages=MAX_PAGES,
                    items_per_page=top,
                    method_name="list_definitions_async",
                    current_skip=current_skip,
                    filter_example="Name eq 'MyQueue'",
                )

    @traced(name="queues_retrieve_definition", run_type="uipath")
    @resource_override(resource_type="queue_definition")
    def retrieve_definition(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> QueueDefinition:
        """Retrieve a queue definition by name or key.

        Args:
            name: Queue name
            key: Queue UUID key
            folder_path: Folder path
            folder_key: Folder UUID key

        Returns:
            QueueDefinition: The queue definition

        Raises:
            LookupError: If the queue is not found

        Examples:
            >>> queue = sdk.queues.retrieve_definition(name="InvoiceQueue")
        """
        if not name and not key:
            raise ValueError("Either 'name' or 'key' must be provided")

        spec = self._retrieve_definition_spec(
            name=name,
            key=key,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()

        items = response.get("value", [])
        if not items:
            raise LookupError(
                f"Queue definition with name '{name}' or key '{key}' not found."
            )
        return QueueDefinition.model_validate(items[0])

    @traced(name="queues_retrieve_definition", run_type="uipath")
    @resource_override(resource_type="queue_definition")
    async def retrieve_definition_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> QueueDefinition:
        """Async version of retrieve_definition()."""
        if not name and not key:
            raise ValueError("Either 'name' or 'key' must be provided")

        spec = self._retrieve_definition_spec(
            name=name,
            key=key,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()

        items = response.get("value", [])
        if not items:
            raise LookupError(
                f"Queue definition with name '{name}' or key '{key}' not found."
            )
        return QueueDefinition.model_validate(items[0])

    @traced(name="queues_create_definition", run_type="uipath")
    def create_definition(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        max_number_of_retries: int = 0,
        accept_automatically_retry: bool = False,
        enforce_unique_reference: bool = False,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> QueueDefinition:
        """Create a new queue definition.

        Args:
            name: Queue name (must be unique within folder)
            description: Optional description
            max_number_of_retries: Max retry attempts (default 0)
            accept_automatically_retry: Auto-retry failed items (default False)
            enforce_unique_reference: Enforce unique references (default False)
            folder_path: Folder path
            folder_key: Folder UUID key

        Returns:
            QueueDefinition: Newly created queue definition

        Examples:
            >>> queue = sdk.queues.create_definition(
            ...     name="InvoiceQueue",
            ...     max_number_of_retries=3,
            ...     enforce_unique_reference=True
            ... )
        """
        spec = self._create_definition_spec(
            name=name,
            description=description,
            max_number_of_retries=max_number_of_retries,
            accept_automatically_retry=accept_automatically_retry,
            enforce_unique_reference=enforce_unique_reference,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        ).json()

        return QueueDefinition.model_validate(response)

    @traced(name="queues_create_definition", run_type="uipath")
    async def create_definition_async(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        max_number_of_retries: int = 0,
        accept_automatically_retry: bool = False,
        enforce_unique_reference: bool = False,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> QueueDefinition:
        """Async version of create_definition()."""
        spec = self._create_definition_spec(
            name=name,
            description=description,
            max_number_of_retries=max_number_of_retries,
            accept_automatically_retry=accept_automatically_retry,
            enforce_unique_reference=enforce_unique_reference,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
        ).json()

        return QueueDefinition.model_validate(response)

    @traced(name="queues_delete_definition", run_type="uipath")
    @resource_override(resource_type="queue_definition")
    def delete_definition(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete a queue definition.

        Args:
            name: Queue name
            key: Queue UUID key
            folder_path: Folder path
            folder_key: Folder UUID key

        Returns:
            None

        Examples:
            >>> sdk.queues.delete_definition(name="OldQueue")
        """
        if not name and not key:
            raise ValueError("Either 'name' or 'key' must be provided")

        if name and not key:
            queue_def = self.retrieve_definition(
                name=name, folder_path=folder_path, folder_key=folder_key
            )
            if queue_def.id is None:
                raise ValueError(
                    f"Queue definition '{name}' was found, but it does not have an id and cannot be deleted."
                )
            key = queue_def.id

        if not isinstance(key, int):
            raise ValueError(f"Invalid queue id: {key}")

        spec = self._delete_definition_spec(
            queue_id=key,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        self.request(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="queues_delete_definition", run_type="uipath")
    @resource_override(resource_type="queue_definition")
    async def delete_definition_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Async version of delete_definition()."""
        if not name and not key:
            raise ValueError("Either 'name' or 'key' must be provided")

        if name and not key:
            queue_def = await self.retrieve_definition_async(
                name=name, folder_path=folder_path, folder_key=folder_key
            )
            if queue_def.id is None:
                raise ValueError(
                    f"Queue definition '{name}' was found, but it does not have an id and cannot be deleted."
                )
            key = queue_def.id

        if not isinstance(key, int):
            raise ValueError(f"Invalid queue id: {key}")

        spec = self._delete_definition_spec(
            queue_id=key,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        await self.request_async(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="queues_exists_definition", run_type="uipath")
    def exists_definition(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Check if queue definition exists.

        Args:
            name: Queue name
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            bool: True if queue exists

        Examples:
            >>> if sdk.queues.exists_definition("InvoiceQueue"):
            ...     print("Queue found")
        """
        try:
            self.retrieve_definition(
                name=name, folder_key=folder_key, folder_path=folder_path
            )
            return True
        except LookupError:
            return False

    @traced(name="queues_exists_definition", run_type="uipath")
    async def exists_definition_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Async version of exists_definition()."""
        try:
            await self.retrieve_definition_async(
                name=name, folder_key=folder_key, folder_path=folder_path
            )
            return True
        except LookupError:
            return False

    # ========== QUEUE ITEMS ==========

    @traced(name="queues_list_items", run_type="uipath")
    def list_items(
        self,
        *,
        queue_name: Optional[str] = None,
        queue_key: Optional[str] = None,
        status: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> Iterator[QueueItem]:
        """List queue items with server-side filtering and auto-pagination.

        Args:
            queue_name: Filter by queue name
            queue_key: Filter by queue UUID key
            status: Filter by status ("New", "InProgress", "Successful", "Failed")
            folder_path: Folder path
            folder_key: Folder key (mutually exclusive with folder_path)
            filter: OData $filter expression
            orderby: OData $orderby expression
            top: Maximum items per page (default 100)
            skip: Number of items to skip

        Yields:
            QueueItem: Queue item instances

        Examples:
            >>> # List all new items in a queue
            >>> for item in sdk.queues.list_items(queue_name="InvoiceQueue", status="New"):
            ...     print(item.reference, item.specific_content)

            >>> # List with custom OData filter
            >>> for item in sdk.queues.list_items(filter="Priority eq 'High'"):
            ...     print(item.reference)
        """
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_items_spec(
                queue_name=queue_name,
                queue_key=queue_key,
                status=status,
                folder_path=folder_path,
                folder_key=folder_key,
                filter=filter,
                orderby=orderby,
                skip=current_skip,
                top=top,
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                yield QueueItem.model_validate(item)

            pages_fetched += 1

            if len(items) < top:
                break

            current_skip += top

        else:
            if items and len(items) == top:
                raise PaginationLimitError.create(
                    max_pages=MAX_PAGES,
                    items_per_page=top,
                    method_name="list_items",
                    current_skip=current_skip,
                    filter_example="Priority eq 'High'",
                )

    @traced(name="queues_list_items", run_type="uipath")
    async def list_items_async(
        self,
        *,
        queue_name: Optional[str] = None,
        queue_key: Optional[str] = None,
        status: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> AsyncIterator[QueueItem]:
        """Async version of list_items() with server-side filtering and auto-pagination.

        Args:
            queue_name: Filter by queue name
            queue_key: Filter by queue UUID key
            status: Filter by status ("New", "InProgress", "Successful", "Failed")
            folder_path: Folder path
            folder_key: Folder key (mutually exclusive with folder_path)
            filter: OData $filter expression
            orderby: OData $orderby expression
            top: Maximum items per page (default 100)
            skip: Number of items to skip

        Yields:
            QueueItem: Queue item instances

        Examples:
            >>> async for item in sdk.queues.list_items_async(queue_name="InvoiceQueue"):
            ...     print(item.reference)
        """
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_items_spec(
                queue_name=queue_name,
                queue_key=queue_key,
                status=status,
                folder_path=folder_path,
                folder_key=folder_key,
                filter=filter,
                orderby=orderby,
                skip=current_skip,
                top=top,
            )
            response = await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
            data = response.json()

            items = data.get("value", [])
            if not items:
                break

            for item in items:
                yield QueueItem.model_validate(item)

            pages_fetched += 1

            if len(items) < top:
                break

            current_skip += top

        else:
            if items and len(items) == top:
                raise PaginationLimitError.create(
                    max_pages=MAX_PAGES,
                    items_per_page=top,
                    method_name="list_items_async",
                    current_skip=current_skip,
                    filter_example="Priority eq 'High'",
                )

    @traced(name="queues_create_item", run_type="uipath")
    def create_item(
        self,
        *,
        queue_name: Optional[str] = None,
        queue_key: Optional[str] = None,
        reference: str,
        specific_content: Dict[str, Any],
        priority: Optional[str] = None,
        defer_date: Optional[datetime] = None,
        due_date: Optional[datetime] = None,
        risk_sla_date: Optional[datetime] = None,
        progress: Optional[str] = None,
        source: Optional[str] = None,
        parent_operation_id: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> QueueItem:
        """Creates a new queue item with explicit parameters.

        Args:
            queue_name: Queue name (alternative to queue_key)
            queue_key: Queue UUID key (alternative to queue_name)
            reference: Unique reference for tracking (REQUIRED)
            specific_content: Queue item data as key-value pairs (REQUIRED)
            priority: Processing priority ("Low", "Normal", "High")
            defer_date: Earliest date/time for processing
            due_date: Latest date/time for processing
            risk_sla_date: Risk SLA date/time
            progress: Business flow progress tracking
            source: Source type of the item
            parent_operation_id: Operation ID that started the job
            folder_path: Folder path
            folder_key: Folder key (mutually exclusive with folder_path)

        Returns:
            QueueItem: The created queue item

        Raises:
            ValueError: If neither queue_name nor queue_key is provided

        Example:
            >>> item = sdk.queues.create_item(
            ...     queue_name="InvoiceQueue",
            ...     reference="INV-001",
            ...     specific_content={"InvoiceNumber": "INV-001", "Amount": 1000},
            ...     priority="High"
            ... )

        Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)
        """
        if queue_name is None and queue_key is None:
            raise ValueError("Either 'queue_name' or 'queue_key' must be provided")

        # Build QueueItem from explicit parameters
        # Use model field names for defined fields, aliases for extra fields
        item_data: Dict[str, Any] = {
            "name": queue_name,
            "specific_content": specific_content,
            "priority": priority,
            "defer_date": defer_date,
            "due_date": due_date,
            "risk_sla_date": risk_sla_date,
            "progress": progress,
            "source": source,
            "parent_operation_id": parent_operation_id,
            "Reference": reference,  # Extra field - not defined in model
        }
        # Remove None values
        item_data = {k: v for k, v in item_data.items() if v is not None}

        queue_item = QueueItem(**item_data)
        spec = self._create_item_spec(
            queue_item, folder_path=folder_path, folder_key=folder_key
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return QueueItem.model_validate(response.json())

    @traced(name="queues_create_item", run_type="uipath")
    async def create_item_async(
        self,
        *,
        queue_name: Optional[str] = None,
        queue_key: Optional[str] = None,
        reference: str,
        specific_content: Dict[str, Any],
        priority: Optional[str] = None,
        defer_date: Optional[datetime] = None,
        due_date: Optional[datetime] = None,
        risk_sla_date: Optional[datetime] = None,
        progress: Optional[str] = None,
        source: Optional[str] = None,
        parent_operation_id: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> QueueItem:
        """Asynchronously creates a new queue item with explicit parameters.

        Args:
            queue_name: Queue name (alternative to queue_key)
            queue_key: Queue UUID key (alternative to queue_name)
            reference: Unique reference for tracking (REQUIRED)
            specific_content: Queue item data as key-value pairs (REQUIRED)
            priority: Processing priority ("Low", "Normal", "High")
            defer_date: Earliest date/time for processing
            due_date: Latest date/time for processing
            risk_sla_date: Risk SLA date/time
            progress: Business flow progress tracking
            source: Source type of the item
            parent_operation_id: Operation ID that started the job
            folder_path: Folder path
            folder_key: Folder key (mutually exclusive with folder_path)

        Returns:
            QueueItem: The created queue item

        Raises:
            ValueError: If neither queue_name nor queue_key is provided

        Example:
            >>> item = await sdk.queues.create_item_async(
            ...     queue_name="InvoiceQueue",
            ...     reference="INV-001",
            ...     specific_content={"InvoiceNumber": "INV-001", "Amount": 1000},
            ...     priority="High"
            ... )

        Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)
        """
        if queue_name is None and queue_key is None:
            raise ValueError("Either 'queue_name' or 'queue_key' must be provided")

        item_data: Dict[str, Any] = {
            "name": queue_name,
            "specific_content": specific_content,
            "priority": priority,
            "defer_date": defer_date,
            "due_date": due_date,
            "risk_sla_date": risk_sla_date,
            "progress": progress,
            "source": source,
            "parent_operation_id": parent_operation_id,
            "Reference": reference,  # Extra field - not defined in model
        }
        # Remove None values
        item_data = {k: v for k, v in item_data.items() if v is not None}

        queue_item = QueueItem(**item_data)
        spec = self._create_item_spec(
            queue_item, folder_path=folder_path, folder_key=folder_key
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )
        return QueueItem.model_validate(response.json())

    @traced(name="queues_create_items", run_type="uipath")
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
        response = self.request(spec.method, url=spec.endpoint, json=spec.json)
        return response.json()

    @traced(name="queues_create_items", run_type="uipath")
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
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json
        )
        return response.json()

    @traced(name="queues_create_transaction_item", run_type="uipath")
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
        response = self.request(spec.method, url=spec.endpoint, json=spec.json)
        return response.json()

    @traced(name="queues_create_transaction_item", run_type="uipath")
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
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json
        )
        return response.json()

    @traced(name="queues_update_progress_of_transaction_item", run_type="uipath")
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
        response = self.request(spec.method, url=spec.endpoint, json=spec.json)
        return response.json()

    @traced(name="queues_update_progress_of_transaction_item", run_type="uipath")
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
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json
        )
        return response.json()

    @traced(name="queues_complete_transaction_item", run_type="uipath")
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
        response = self.request(spec.method, url=spec.endpoint, json=spec.json)
        return response.json()

    @traced(name="queues_complete_transaction_item", run_type="uipath")
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
        response = await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json
        )
        return response.json()

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _list_items_spec(
        self,
        queue_name: Optional[str],
        queue_key: Optional[str],
        status: Optional[str],
        folder_path: Optional[str],
        folder_key: Optional[str],
        filter: Optional[str],
        orderby: Optional[str],
        skip: int,
        top: int,
    ) -> RequestSpec:
        """Build OData request for listing queue items."""
        filters = []

        if queue_name:
            escaped_name = queue_name.replace("'", "''")
            filters.append(f"QueueDefinition/Name eq '{escaped_name}'")

        if queue_key:
            escaped_key = queue_key.replace("'", "''")
            filters.append(f"QueueDefinition/Key eq '{escaped_key}'")

        if status:
            filters.append(f"Status eq '{status}'")

        if filter:
            filters.append(filter)

        filter_str = " and ".join(filters) if filters else None

        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if filter_str:
            params["$filter"] = filter_str
        if orderby:
            params["$orderby"] = orderby

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/QueueItems"),
            params=params,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _create_item_spec(
        self,
        item: QueueItem,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        json_payload = {"itemData": item.model_dump(exclude_unset=True, by_alias=True)}

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

    def _list_definitions_spec(
        self,
        folder_path: Optional[str],
        folder_key: Optional[str],
        name: Optional[str],
        filter: Optional[str],
        orderby: Optional[str],
        skip: int,
        top: int,
    ) -> RequestSpec:
        """Build OData request for listing queue definitions."""
        filters = []
        if name:
            escaped_name = name.replace("'", "''")
            filters.append(f"contains(tolower(Name), tolower('{escaped_name}'))")
        if filter:
            filters.append(filter)

        filter_str = " and ".join(filters) if filters else None

        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if filter_str:
            params["$filter"] = filter_str
        if orderby:
            params["$orderby"] = orderby

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/QueueDefinitions"),
            params=params,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_definition_spec(
        self,
        name: Optional[str],
        key: Optional[str],
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        """Build request for retrieving queue definition."""
        filters = []
        if name:
            escaped_name = name.replace("'", "''")
            filters.append(f"Name eq '{escaped_name}'")
        if key:
            escaped_key = key.replace("'", "''")
            filters.append(f"Key eq '{escaped_key}'")

        filter_str = " or ".join(filters) if filters else None

        params: Dict[str, Any] = {"$top": 1}
        if filter_str:
            params["$filter"] = filter_str

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/QueueDefinitions"),
            params=params,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _create_definition_spec(
        self,
        name: str,
        description: Optional[str],
        max_number_of_retries: int,
        accept_automatically_retry: bool,
        enforce_unique_reference: bool,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        """Build request for creating queue definition."""
        body = {
            "Name": name,
            "MaxNumberOfRetries": max_number_of_retries,
            "AcceptAutomaticallyRetry": accept_automatically_retry,
            "EnforceUniqueReference": enforce_unique_reference,
        }
        if description:
            body["Description"] = description

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/orchestrator_/odata/QueueDefinitions"),
            json=body,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _delete_definition_spec(
        self,
        queue_id: int,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        """Build request for deleting queue definition by ID."""
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"/orchestrator_/odata/QueueDefinitions({queue_id})"),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
