# UiPath Coded Agent: Resource Bindings Demo

## Overview

This sample demonstrates how to use resource bindings within your coded agent to enable dynamic resource replacement at runtime. It showcases how UiPath resources (assets, connections, apps, indexes, buckets and processes) defined in your agent code can be mapped and replaced with different resources when the agent is published to UiPath Orchestrator.

## Features

- **Dynamic Resource Binding**: Define resources in code that can be replaced at deployment
- **Multiple Resource Types**: Demonstrates bindings for all major UiPath resource types
- **Runtime Flexibility**: Replace resources without modifying code
- **Environment Separation**: Use different resources for development, staging, and production

## Prerequisites

1. Python 3.11+
2. UiPath Platform account with access to Orchestrator
3. Access to the following resource types in your Orchestrator:
   - Assets
   - Connections (Integration Service)
   - Apps (Action Center)
   - Context Grounding Indexes
   - Storage Buckets
   - Processes

## Setup and Configuration

### 1. Install Dependencies

```bash
# Install uv if not already installed
pip install uv

# Install dependencies
uv sync
```

### 2. Understanding Resource Bindings

The agent uses various UiPath SDK methods to interact with resources. The `bindings.json` file maps these resources with their default values:

- **Assets**: `asset_name` in folder `folder_key`
- **Connections**: `connection_key` (e.g., Salesforce, Slack)
- **Apps**: `app_name` in folder `app_folder_path`
- **Indexes**: `index_name` in folder `folder_path`
- **Buckets**: `bucket_name` in folder `folder_path`
- **Processes**: `process_name` in folder `folder_path`

## How It Works

1. **Code Definition**: The agent code defines interactions with various UiPath resources using their identifiers
2. **Binding Definition**: The bindings.json file contains the resources that are overridable at runtime
3. **Publishing**: When published to Orchestrator, each resource binding becomes configurable
4. **Runtime Replacement**: In Orchestrator, you can select replacement resources of the same type

### Resource Replacement in Orchestrator

When you publish this agent to UiPath Orchestrator, for each resource defined in `bindings.json`, you can select a replacement resource of the same kind from the resources you have access to:

![Package requirements page](../../docs/sample_images/resource-overrides/package-requirements.png)

*Screenshot: UiPath Orchestrator showing resource replacement options for each bound resource*

This allows you to:
- Use test resources in development environments
- Switch to production resources without code changes
- Share agents across teams with different resource configurations
- Maintain environment-specific configurations easily

## Running the Agent

### Local Development

```bash
# Run the agent locally (will use default resource values defined in code)
uv run uipath run main.py
```

### On UiPath Platform

1. **Authenticate with UiPath**:
   ```bash
   uv run uipath auth
   ```

2. **Package the agent**:
   ```bash
   uv run uipath pack
   ```

3. **Publish to your workspace**:
   ```bash
   uv run uipath publish --my-workspace
   ```

4. **Configure Resources in Orchestrator**:
   - Navigate to your agent in Orchestrator
   - For each resource in the bindings, select the appropriate replacement
   - Save the configuration

5. **Run the Agent**:
   - Execute the agent from Orchestrator
   - The agent will use the configured replacement resources

## Implementation Details

### Resource Types and Methods

The agent demonstrates the following resource interactions:

| Resource Type | SDK Method | Purpose |
|---------------|------------|---------|
| **Asset** | `uipath.assets.retrieve_async()` | Retrieve asset values |
| **Connection** | `uipath.connections.retrieve_async()` | Get connection details |
| **App (Action)** | `uipath.actions.create_async()` | Create action items |
| **Index** | `uipath.context_grounding.retrieve_async()` | Access context grounding data |
| **Bucket** | `uipath.buckets.retrieve_async()` | Access storage buckets |
| **Process** | `uipath.processes.invoke_async()` | Trigger process execution |

### Output Structure

The agent returns a `Response` object containing details about each accessed resource:

```python
class Resource(BaseModel):
    name: str
    value: Any

class Response(BaseModel):
    resources: list[Resource] = []
```

