# UiPath Coded Agent: Asset Value Checker

This project demonstrates how to create a Python-based UiPath Coded Agent that connects as an External Application to UiPath Orchestrator, retrieves an asset, and validates its IntValue against custom rules.

## Overview

The agent uses the UiPath Python SDK to:

* Connect to UiPath Orchestrator as an external application
* Authenticate via the Client Credentials flow (Client ID + Client Secret)
* Retrieve a specific asset from a given folder
* Check whether the asset has an integer value and validate it against a range (100–1000)
* Return a descriptive message with the validation result

## How to Set Up

### Step 1: Install UiPath Python SDK

1. Open it with your prefered editor
2. In terminal run:
```bash
uv init
uv add uipath
uv run uipath init
```

### Step 2: Configure Environment Variables

```bash
UIPATH_CLIENT_SECRET=your-client-secret
```

### Step 3: Run the Agent

Format your `input.json` file to follow this format:

```
{
  "asset_name": "test-asset",
  "folder_path": "TestFolder"
}
```

Input File Parameters:

`asset_name`: The name of the UiPath asset you want the agent to validate.

`folder_path`: The path of the folder in Orchestrator where the asset exists.

To execute the agent, use the following command:
```bash
uipath run --input-file input.json
```

### Step 3: Understanding the Event Flow

When this agent runs, it will:
1. Pass the configured input values (`asset_name` and `folder_path`) into the agent
2. Connect to Orchestrator using Client Credentials (Client ID + Client Secret)
3. Retrieve the specified asset from the given folder
4. Check whether the asset contains an IntValue and validates it against the allowed range (100–1000)
5. Return a message with the validation result

### Step 4: Publish Your Coded Agent

1. Use `uipath pack` and `uipath publish` to create and publish the package
2. Create an Orchestrator Automation from the published process
