# UiPath Coded Agent: Queue Item Manager

This project demonstrates how to create a Python-based UiPath Coded Agent that connects to UiPath Orchestrator and manages queue items with multiple interaction patterns.

## Overview

The agent uses the UiPath Python SDK to:

* Connect to UiPath Orchestrator
* Add queue items using multiple methods (single, bulk, dictionary, with dates)
* List and view queue items
* Return detailed operation results

## Prerequisites

* [UV package manager](https://docs.astral.sh/uv/) installed
* UiPath Orchestrator access with appropriate credentials
* At least one queue configured in your Orchestrator instance

## Setup

### Step 1: Create and Activate Virtual Environment

```bash
uv venv
```

Activate the virtual environment:
- **Windows**: `.venv\Scripts\activate`
- **Linux/Mac**: `source .venv/bin/activate`

### Step 2: Install Dependencies

```bash
uv sync
```

### Step 3: Initialize the Agent

```bash
uv run uipath init
```

### Step 4: Prepare Input Data

The agent supports multiple operations. Format your `input.json` file based on the operation:

#### Add Single Item

```json
{
  "operation": "add_single",
  "queue_name": "TestQueue",
  "items": [
    {
      "reference": "ITEM-001",
      "priority": "Normal",
      "specific_content": {
        "customer_id": "CUST-001",
        "order_number": "ORD-2024-001"
      }
    }
  ]
}
```

#### Add Bulk Items

```json
{
  "operation": "add_bulk",
  "queue_name": "TestQueue",
  "items": [
    {
      "reference": "ITEM-001",
      "priority": "High",
      "specific_content": {"data": "item1"}
    },
    {
      "reference": "ITEM-002",
      "priority": "Low",
      "specific_content": {"data": "item2"}
    }
  ]
}
```

#### Add Item via Dictionary

```json
{
  "operation": "add_dict",
  "queue_name": "TestQueue",
  "items": [
    {
      "reference": "ITEM-DICT-001",
      "priority": "High",
      "specific_content": {
        "transaction_type": "payment"
      }
    }
  ]
}
```

#### Add Item with Date Constraints

```json
{
  "operation": "add_with_dates",
  "queue_name": "TestQueue",
  "items": [
    {
      "reference": "TIME-SENSITIVE-001",
      "priority": "High",
      "specific_content": {"task": "urgent"},
      "defer_date": "2026-02-13 12:00:00.000",
      "due_date": "2026-02-14 11:00:00.000"
    }
  ]
}
```

#### List Queue Items

```json
{
  "operation": "list",
  "queue_name": "TestQueue"
}
```

**Input Parameters:**
- `operation` (required): Operation to perform
  - `add_single`: Add a single queue item using QueueItem object
  - `add_dict`: Add a single queue item using dictionary method
  - `add_bulk`: Add multiple queue items in one operation
  - `add_with_dates`: Add item with defer/due date constraints
  - `list`: List all queue items
- `queue_name` (required): The name of the UiPath queue
- `items` (optional): Array of queue items (required for add operations)
  - `reference` (optional): Unique reference identifier
  - `priority` (optional): Priority level (Low, Normal, High)
  - `specific_content` (optional): Custom data payload
  - `defer_date` (optional): Earliest processing date in UTC format
  - `due_date` (optional): Latest processing date in UTC format

### Step 5: Run the Agent

Execute the agent locally:

```bash
uipath run main --input-file input.json
```

## How It Works

When this agent runs, it will:

1. Load input values (`operation`, `queue_name`, and optionally `items`)
2. Connect to UiPath Orchestrator
3. Execute the specified operation:
   - **add_single**: Creates a single queue item using QueueItem object
   - **add_dict**: Creates a single queue item using dictionary method
   - **add_bulk**: Creates multiple queue items in bulk with independent processing
   - **add_with_dates**: Creates a time-sensitive queue item with defer/due dates
   - **list**: Retrieves and displays queue items (up to 10 shown)
4. Return a detailed message with the operation results

**Sample Outputs:**

```
# add_single
Successfully added item 'ITEM-001' (ID: 12345) to queue 'TestQueue'

# add_bulk
Bulk operation: 3 item(s) added successfully, 0 failed in queue 'TestQueue'

# add_with_dates
Successfully added time-sensitive item (ID: 12346) with defer date: 2026-02-13T12:00:00Z

# list
Found 5 queue item(s):
ID: 12345 | Status: New | Priority: Low | Ref: ITEM-001
ID: 12346 | Status: New | Priority: High | Ref: ITEM-002
...
```

## Queue Item Properties

Each queue item supports the following properties:

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `reference` | str | No | Optional unique identifier (max 128 chars) |
| `priority` | str | No | Low, Normal, or High (default: None) |
| `specific_content` | dict | No | Custom data payload for the work item |
| `defer_date` | str | No | Earliest processing date (UTC format: "YYYY-MM-DD HH:MM:SS.mmm") |
| `due_date` | str | No | Latest processing date (UTC format: "YYYY-MM-DD HH:MM:SS.mmm") |

## Operations Reference

### add_single
Adds a single queue item using the QueueItem class. This is the standard method for adding items with full type safety.

### add_dict
Adds a single queue item using a dictionary. Alternative approach that demonstrates dictionary-based item creation.

### add_bulk
Adds multiple queue items in a single operation using `CommitType.PROCESS_ALL_INDEPENDENTLY`. Each item is processed independently, and the operation reports success/failure counts.

### add_with_dates
Adds a queue item with defer and due date constraints. Useful for time-sensitive processing where items should not be processed before a certain time or must be completed by a deadline.

### list
Lists all queue items from the queue. Returns up to 10 items with their ID, Status, Priority, and Reference. Indicates if more items exist beyond the displayed limit.

## Publish Your Coded Agent

Once tested locally, publish your agent to Orchestrator:

1. Pack the agent:
   ```bash
   uipath pack
   ```

2. Publish to Orchestrator:
   ```bash
   uipath publish
   ```
