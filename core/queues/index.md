## QueuesService

Service for managing UiPath queues and queue items.

Queues are a fundamental component of UiPath automation that enable distributed and scalable processing of work items.

### complete_transaction_item

```
complete_transaction_item(transaction_key, result)
```

Completes a transaction item with the specified result.

Parameters:

| Name              | Type             | Description                                       | Default                                                                                    |
| ----------------- | ---------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `transaction_key` | `str`            | Unique identifier of the transaction to complete. | *required*                                                                                 |
| `result`          | \`dict[str, Any] | TransactionItemResult\`                           | Result data for the transaction, either as a dictionary or TransactionItemResult instance. |

Returns:

| Name       | Type       | Description                                          |
| ---------- | ---------- | ---------------------------------------------------- |
| `Response` | `Response` | HTTP response confirming the transaction completion. |

Related Activity: [Set Transaction Status](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-status)

### complete_transaction_item_async

```
complete_transaction_item_async(transaction_key, result)
```

Asynchronously completes a transaction item with the specified result.

Parameters:

| Name              | Type             | Description                                       | Default                                                                                    |
| ----------------- | ---------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `transaction_key` | `str`            | Unique identifier of the transaction to complete. | *required*                                                                                 |
| `result`          | \`dict[str, Any] | TransactionItemResult\`                           | Result data for the transaction, either as a dictionary or TransactionItemResult instance. |

Returns:

| Name       | Type       | Description                                          |
| ---------- | ---------- | ---------------------------------------------------- |
| `Response` | `Response` | HTTP response confirming the transaction completion. |

Related Activity: [Set Transaction Status](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-status)

### create_item

```
create_item(item)
```

Creates a new queue item in the Orchestrator.

Parameters:

| Name   | Type             | Description | Default                                                        |
| ------ | ---------------- | ----------- | -------------------------------------------------------------- |
| `item` | \`dict[str, Any] | QueueItem\` | Queue item data, either as a dictionary or QueueItem instance. |

Returns:

| Name       | Type       | Description                                              |
| ---------- | ---------- | -------------------------------------------------------- |
| `Response` | `Response` | HTTP response containing the created queue item details. |

Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)

### create_item_async

```
create_item_async(item)
```

Asynchronously creates a new queue item in the Orchestrator.

Parameters:

| Name   | Type             | Description | Default                                                        |
| ------ | ---------------- | ----------- | -------------------------------------------------------------- |
| `item` | \`dict[str, Any] | QueueItem\` | Queue item data, either as a dictionary or QueueItem instance. |

Returns:

| Name       | Type       | Description                                              |
| ---------- | ---------- | -------------------------------------------------------- |
| `Response` | `Response` | HTTP response containing the created queue item details. |

Related Activity: [Add Queue Item](https://docs.uipath.com/ACTIVITIES/other/latest/workflow/add-queue-item)

### create_items

```
create_items(items, queue_name, commit_type)
```

Creates multiple queue items in bulk.

Parameters:

| Name          | Type                   | Description                                             | Default                                                                        |
| ------------- | ---------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `items`       | \`list\[dict[str, Any] | QueueItem\]\`                                           | List of queue items to create, each either a dictionary or QueueItem instance. |
| `queue_name`  | `str`                  | Name of the target queue.                               | *required*                                                                     |
| `commit_type` | `CommitType`           | Type of commit operation to use for the bulk operation. | *required*                                                                     |

Returns:

| Name       | Type       | Description                                         |
| ---------- | ---------- | --------------------------------------------------- |
| `Response` | `Response` | HTTP response containing the bulk operation result. |

### create_items_async

```
create_items_async(items, queue_name, commit_type)
```

Asynchronously creates multiple queue items in bulk.

Parameters:

| Name          | Type                   | Description                                             | Default                                                                        |
| ------------- | ---------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `items`       | \`list\[dict[str, Any] | QueueItem\]\`                                           | List of queue items to create, each either a dictionary or QueueItem instance. |
| `queue_name`  | `str`                  | Name of the target queue.                               | *required*                                                                     |
| `commit_type` | `CommitType`           | Type of commit operation to use for the bulk operation. | *required*                                                                     |

Returns:

| Name       | Type       | Description                                         |
| ---------- | ---------- | --------------------------------------------------- |
| `Response` | `Response` | HTTP response containing the bulk operation result. |

### create_transaction_item

```
create_transaction_item(item, no_robot=False)
```

Creates a new transaction item in a queue.

Parameters:

| Name       | Type             | Description                                                                      | Default                                                                    |
| ---------- | ---------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `item`     | \`dict[str, Any] | TransactionItem\`                                                                | Transaction item data, either as a dictionary or TransactionItem instance. |
| `no_robot` | `bool`           | If True, the transaction will not be associated with a robot. Defaults to False. | `False`                                                                    |

Returns:

| Name       | Type       | Description                                            |
| ---------- | ---------- | ------------------------------------------------------ |
| `Response` | `Response` | HTTP response containing the transaction item details. |

### create_transaction_item_async

```
create_transaction_item_async(item, no_robot=False)
```

Asynchronously creates a new transaction item in a queue.

Parameters:

| Name       | Type             | Description                                                                      | Default                                                                    |
| ---------- | ---------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `item`     | \`dict[str, Any] | TransactionItem\`                                                                | Transaction item data, either as a dictionary or TransactionItem instance. |
| `no_robot` | `bool`           | If True, the transaction will not be associated with a robot. Defaults to False. | `False`                                                                    |

Returns:

| Name       | Type       | Description                                            |
| ---------- | ---------- | ------------------------------------------------------ |
| `Response` | `Response` | HTTP response containing the transaction item details. |

### list_items

```
list_items()
```

Retrieves a list of queue items from the Orchestrator.

Returns:

| Name       | Type       | Description                                       |
| ---------- | ---------- | ------------------------------------------------- |
| `Response` | `Response` | HTTP response containing the list of queue items. |

### list_items_async

```
list_items_async()
```

Asynchronously retrieves a list of queue items from the Orchestrator.

Returns:

| Name       | Type       | Description                                       |
| ---------- | ---------- | ------------------------------------------------- |
| `Response` | `Response` | HTTP response containing the list of queue items. |

### update_progress_of_transaction_item

```
update_progress_of_transaction_item(
    transaction_key, progress
)
```

Updates the progress of a transaction item.

Parameters:

| Name              | Type  | Description                           | Default    |
| ----------------- | ----- | ------------------------------------- | ---------- |
| `transaction_key` | `str` | Unique identifier of the transaction. | *required* |
| `progress`        | `str` | Progress message to set.              | *required* |

Returns:

| Name       | Type       | Description                                   |
| ---------- | ---------- | --------------------------------------------- |
| `Response` | `Response` | HTTP response confirming the progress update. |

Related Activity: [Set Transaction Progress](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-progress)

### update_progress_of_transaction_item_async

```
update_progress_of_transaction_item_async(
    transaction_key, progress
)
```

Asynchronously updates the progress of a transaction item.

Parameters:

| Name              | Type  | Description                           | Default    |
| ----------------- | ----- | ------------------------------------- | ---------- |
| `transaction_key` | `str` | Unique identifier of the transaction. | *required* |
| `progress`        | `str` | Progress message to set.              | *required* |

Returns:

| Name       | Type       | Description                                   |
| ---------- | ---------- | --------------------------------------------- |
| `Response` | `Response` | HTTP response confirming the progress update. |

Related Activity: [Set Transaction Progress](https://docs.uipath.com/activities/other/latest/workflow/set-transaction-progress)
