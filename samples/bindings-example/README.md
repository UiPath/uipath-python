# Bindings Example

This example demonstrates how to use the UiPath Bindings feature to manage resource references in your code.

## What are Bindings?

Bindings allow you to decouple your code from specific resource names in Orchestrator. Instead of hardcoding asset names, process names, or queue names, you use binding keys that map to the actual resource names in your `uipath.json` configuration file.

## Benefits

- **Environment Independence**: Easily switch between development, staging, and production environments
- **Code Reusability**: Use the same code with different resource names
- **Better Maintainability**: Change resource names in one place (uipath.json) instead of throughout your code

## Setup

### 1. Initialize your project

```bash
uipath init main.py
```

This creates a `uipath.json` file in your project.

### 2. Create bindings

Use the CLI to create bindings for your resources:

```bash
# Create an asset binding
uipath bindings create my-config-asset -t asset -n "MyConfigurationAsset"

# Create a process binding with folder path
uipath bindings create my-process -t process -n "MyProcessName" -f "/Shared/Production"

# Create a queue binding
uipath bindings create my-queue -t queue -n "MyQueueName"
```

### 3. Configure environment variables

Set the required environment variables:

```bash
export UIPATH_URL="https://cloud.uipath.com/your-org/your-tenant"
export UIPATH_ACCESS_TOKEN="your_access_token"
export UIPATH_FOLDER_PATH="/Shared/YourFolder"
```

### 4. View your bindings

List all configured bindings:

```bash
uipath bindings list
```

## Usage in Code

### Basic Usage

```python
from uipath import UiPath, Bindings

client = UiPath()

# Get asset name from binding
asset_name = Bindings.get("my-config-asset")
asset = client.assets.retrieve(name=asset_name)
```

### With Folder Path

```python
# Get both name and folder path
asset_name, folder_path = Bindings.get_with_folder("my-config-asset")
asset = client.assets.retrieve(name=asset_name, folder_path=folder_path)
```

### With Default Values

```python
# Provide a default if binding doesn't exist
asset_name = Bindings.get("optional-asset", default="DefaultAsset")
```

### Different Resource Types

```python
# Process binding
process_name = Bindings.get("my-process", resource_type="process")
client.processes.invoke(name=process_name)

# Queue binding
queue_name = Bindings.get("my-queue", resource_type="queue")
client.queues.add_item(name=queue_name, data={"key": "value"})
```

## The uipath.json Structure

After creating bindings, your `uipath.json` will look like this:

```json
{
    "entryPoints": [...],
    "bindings": {...},
    "runtime": {
        "internalArguments": {
            "resourceOverwrites": {
                "asset.my-config-asset": {
                    "name": "MyConfigurationAsset"
                },
                "process.my-process": {
                    "name": "MyProcessName",
                    "folderPath": "/Shared/Production"
                }
            }
        }
    }
}
```

## Managing Bindings

### Create a binding
```bash
uipath bindings create <binding-key> -t <type> -n <name> [-f <folder>]
```

### List all bindings
```bash
uipath bindings list
```

### Remove a binding
```bash
uipath bindings remove <binding-key> -t <type>
```

## Running the Example

```bash
cd samples/bindings-example
uipath run main.py --input '{"message": "Hello!"}'
```

## Different Environments

The power of bindings becomes clear when deploying to different environments:

### Development (uipath.json)
```json
"resourceOverwrites": {
    "asset.my-config-asset": {
        "name": "DevConfigAsset"
    }
}
```

### Production (uipath.json)
```json
"resourceOverwrites": {
    "asset.my-config-asset": {
        "name": "ProdConfigAsset"
    }
}
```

Your code remains the same:
```python
asset_name = Bindings.get("my-config-asset")
```

But it retrieves different assets depending on the environment!
