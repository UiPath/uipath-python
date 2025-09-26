# UiPath Coded Agent: Asset Value Checker

This project demonstrates how to create a Python-based UiPath Coded Agent that connects as an External Application to UiPath Orchestrator, retrieves an asset, and validates its IntValue against custom rules.

## Overview

The agent uses the UiPath Python SDK to:

* Connect to UiPath Orchestrator as an external application
* Authenticate via the Client Credentials flow (Client ID + Client Secret)
* Retrieve a specific asset from a given folder
* Check whether the asset has an integer value and validate it against a range (100–1000)
* Return a descriptive message with the validation result

## Prerequisites

* [UV package manager](https://docs.astral.sh/uv/) installed
* UiPath Orchestrator access
* An External Application configured in UiPath with the `OR.Assets` scope

You can learn how to create and setup your own External Application from the [UiPath documentation](https://docs.uipath.com/automation-cloud/automation-cloud/latest/admin-guide/managing-external-applications).

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

### Step 3: Configure the Application

1. **Edit `main.py`** (lines 13, 16) and replace the placeholder values:
   - `UIPATH_CLIENT_ID`: Replace `"EXTERNAL_APP_CLIENT_ID_HERE"` with your External Application's Client ID
   - `UIPATH_URL`: Replace `"base_url"` with your Orchestrator URL (e.g., `"https://cloud.uipath.com/your_org/your_tenant"`)

2. **Set Environment Variables**

   Create a `.env` file in the project directory or set the environment variable:
   ```bash
   UIPATH_CLIENT_SECRET=your-client-secret-here
   ```

### Step 4: Initialize the Agent

```bash
uv run uipath init
```

### Step 5: Prepare Input Data

Format your `input.json` file with the following structure:

```json
{
  "asset_name": "test-asset",
  "folder_path": "TestFolder"
}
```

**Input Parameters:**
- `asset_name`: The name of the UiPath asset to validate
- `folder_path`: The folder path in Orchestrator where the asset is located

### Step 6: Run the Agent

Execute the agent locally:

```bash
uipath run --input-file input.json
```

## How It Works

When this agent runs, it will:

1. Load input values (`asset_name` and `folder_path`)
2. Connect to Orchestrator using Client Credentials authentication
3. Retrieve the specified asset from the given folder
4. Validate the asset's IntValue against the allowed range (100–1000)
5. Return a descriptive message with the validation result

**Possible Outputs:**
- "Asset not found." — Asset doesn't exist
- "Asset does not have an IntValue." — Asset exists but has no integer value
- "Asset '<name>' has a valid IntValue: <value>" — IntValue is within range
- "Asset '<name>' has an out-of-range IntValue: <value>" — IntValue is outside range

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

