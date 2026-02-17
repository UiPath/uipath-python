import logging
from typing import Any
from pydantic import BaseModel, Field
from uipath.platform import UiPath
from uipath.platform.orchestrator import QueueItem, CommitType
from uipath.tracing import traced

logger = logging.getLogger(__name__)

class QueueItemData(BaseModel):
    """Data structure for a queue item.

    Attributes:
        reference (str | None): Optional reference identifier.
        priority (str | None): Priority level (Low, Normal, High).
        specific_content (dict[str, Any]): Custom data payload.
        defer_date (str | None): Earliest processing date in UTC format.
        due_date (str | None): Latest processing date in UTC format.
    """
    reference: str | None = None
    priority: str | None = None
    specific_content: dict[str, Any] = Field(default_factory=dict)
    defer_date: str | None = None
    due_date: str | None = None

class AgentInput(BaseModel):
    """Input data structure for the UiPath agent.

    Attributes:
        operation (str): Operation to perform (add_single, add_bulk, add_dict, add_with_dates, list).
        queue_name (str): The name of the queue to interact with.
        items (list[QueueItemData] | None): List of queue items for add operations.
    """
    operation: str
    queue_name: str
    items: list[QueueItemData] | None = None

def add_single_queue_item(client: UiPath, queue_name: str, item_data: QueueItemData) -> dict[str, Any]:
    """Add a single queue item using QueueItem object.

    Args:
        client (UiPath): The UiPath client instance.
        queue_name (str): The name of the queue.
        item_data (QueueItemData): Item data to add.

    Returns:
        dict: Result from the API.
    """
    queue_item = QueueItem(
        name=queue_name,
        priority=item_data.priority,
        specific_content=item_data.specific_content,
        reference=item_data.reference,
        defer_date=item_data.defer_date,
        due_date=item_data.due_date
    )
    return client.queues.create_item(queue_item)

def add_queue_item_with_dict(client: UiPath, queue_name: str, item_data: QueueItemData) -> dict[str, Any]:
    """Add a queue item using dictionary method.

    Args:
        client (UiPath): The UiPath client instance.
        queue_name (str): The name of the queue.
        item_data (QueueItemData): Item data to add.

    Returns:
        dict: Result from the API.
    """
    item_dict = {
        "name": queue_name,
        "priority": item_data.priority,
        "specific_content": item_data.specific_content,
        "reference": item_data.reference
    }
    return client.queues.create_item(item_dict)

def add_multiple_queue_items(client: UiPath, queue_name: str, items: list[QueueItemData]) -> dict[str, Any]:
    """Add multiple queue items in bulk.

    Args:
        client (UiPath): The UiPath client instance.
        queue_name (str): The name of the queue.
        items (list[QueueItemData]): List of items to add.

    Returns:
        dict: Result from the API with success/failure counts.
    """
    queue_items = []
    for item_data in items:
        queue_item = QueueItem(
            name=queue_name,
            priority=item_data.priority,
            specific_content=item_data.specific_content,
            reference=item_data.reference
        )
        queue_items.append(queue_item)

    return client.queues.create_items(
        items=queue_items,
        queue_name=queue_name,
        commit_type=CommitType.PROCESS_ALL_INDEPENDENTLY
    )

def add_items_with_dates(client: UiPath, queue_name: str, item_data: QueueItemData) -> dict[str, Any]:
    """Add queue items with defer and due dates.

    Args:
        client (UiPath): The UiPath client instance.
        queue_name (str): The name of the queue.
        item_data (QueueItemData): Item data with date constraints.

    Returns:
        dict: Result from the API.
    """
    queue_item = QueueItem(
        name=queue_name,
        priority=item_data.priority,
        specific_content=item_data.specific_content,
        reference=item_data.reference,
        defer_date=item_data.defer_date,
        due_date=item_data.due_date
    )
    return client.queues.create_item(queue_item)

def list_queue_items(client: UiPath) -> dict[str, Any]:
    """List all queue items.

    Args:
        client (UiPath): The UiPath client instance.

    Returns:
        dict: Result containing queue items.
    """
    return client.queues.list_items()

@traced()
def main(input: AgentInput) -> str:
    """Main entry point for the agent.

    Args:
        input (AgentInput): The input containing operation and queue details.

    Returns:
        str: Message with the result of the queue operation.
    """
    try:
        client = UiPath()

        if input.operation == "add_single":
            if not input.items or len(input.items) == 0:
                return "Error: No item provided for add_single operation"
            result = add_single_queue_item(client, input.queue_name, input.items[0])
            return f"Successfully added item '{result.get('Reference')}' (ID: {result.get('Id')}) to queue '{input.queue_name}'"

        elif input.operation == "add_dict":
            if not input.items or len(input.items) == 0:
                return "Error: No item provided for add_dict operation"
            result = add_queue_item_with_dict(client, input.queue_name, input.items[0])
            return f"Successfully added item via dictionary (ID: {result.get('Id')}) to queue '{input.queue_name}'"

        elif input.operation == "add_bulk":
            if not input.items or len(input.items) == 0:
                return "Error: No items provided for add_bulk operation"
            result = add_multiple_queue_items(client, input.queue_name, input.items)
            failed = len(result.get('FailedItems', []))
            success = len(input.items) - failed
            return f"Bulk operation: {success} item(s) added successfully, {failed} failed in queue '{input.queue_name}'"

        elif input.operation == "add_with_dates":
            if not input.items or len(input.items) == 0:
                return "Error: No item provided for add_with_dates operation"
            result = add_items_with_dates(client, input.queue_name, input.items[0])
            return f"Successfully added time-sensitive item (ID: {result.get('Id')}) with defer date: {result.get('DeferDate')}"

        elif input.operation == "list":
            result = list_queue_items(client)
            items = result.get('value', [])
            if len(items) == 0:
                return "No items found in the queue"
            item_summary = []
            for item in items[:10]:
                item_summary.append(f"ID: {item.get('Id')} | Status: {item.get('Status')} | Priority: {item.get('Priority')} | Ref: {item.get('Reference')}")
            summary = "\n".join(item_summary)
            total = len(items)
            return f"Found {total} queue item(s):\n{summary}" + (f"\n... and {total - 10} more items" if total > 10 else "")

        else:
            return f"Error: Unknown operation '{input.operation}'. Valid operations: add_single, add_dict, add_bulk, add_with_dates, list"

    except Exception as e:
        logger.exception(f"Operation failed: {input.operation}")
        return f"Failed to perform '{input.operation}' on queue '{input.queue_name}': {str(e)}"
