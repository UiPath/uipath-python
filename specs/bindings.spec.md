# UiPath Resources Configuration Specification

## Overview

The resources configuration file defines bindings for UiPath resources including assets, processes, buckets, indexes, apps and connections. This file enables declarative configuration of resource references used throughout your UiPath project.

**File Name:** `bindings.json`

---

## File Structure

```json
{
  "$schema": "https://cloud.uipath.com/draft/2024-12/bindings",
  "version": "2.0",
  "resources": [
    { ... },
    { ... }
  ]
}
```

---

## Top-Level Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `$schema` | `string` | No | Reference to JSON schema for IDE support |
| `version` | `string` | Yes | Configuration version (currently `"2.0"`) |
| `resources` | `array` | Yes | Array of resource binding definitions |

---

## Resource Types

The configuration supports multiple resource types:

1. **asset** - Orchestrator assets
2. **process** - Workflow processes
3. **bucket** - Storage buckets
4. **index** - Search indexes
5. **apps** - Action center apps
6. **connection** - External connections


---

## Resource Structure

Each resource in the `resources` array has the following structure:

```json
{
  "resource": "asset|process|bucket|index|connection",
  "key": "unique_key",
  "value": { ... },
  "metadata": { ... }
}
```

### Common Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `resource` | `string` | Yes | Resource type (one of the five types) |
| `key` | `string` | Yes | Unique identifier for this resource |
| `value` | `object` | Yes | Resource-specific configuration |
| `metadata` | `object` | No | Additional metadata for the binding |

---

## Resource-Specific Configurations

### 1. Asset

Assets are configuration values stored in Orchestrator.

**Key Format:** `asset_name.folder_key`

**Example:**

```json
{
  "resource": "asset",
  "key": "DatabaseConnectionString.Production",
  "value": {
    "name": {
      "defaultValue": "DatabaseConnectionString",
      "isExpression": false,
      "displayName": "Name"
    },
    "folderPath": {
      "defaultValue": "Production",
      "isExpression": false,
      "displayName": "Folder Path"
    }
  },
  "metadata": {
    "ActivityName": "retrieve_async",
    "BindingsVersion": "2.2",
    "DisplayLabel": "FullName"
  }
}
```

**Common Metadata:**
- `ActivityName`: Typically `"retrieve_async"`
- `BindingsVersion`: `"2.2"`
- `DisplayLabel`: `"FullName"`

---

### 2. Process

Processes are workflow definitions that can be invoked.

**Key Format:** `process_name.folder_path`

**Example:**

```json
{
  "resource": "process",
  "key": "DataProcessingWorkflow.Shared",
  "value": {
    "name": {
      "defaultValue": "DataProcessingWorkflow",
      "isExpression": false,
      "displayName": "Name"
    },
    "folderPath": {
      "defaultValue": "Shared",
      "isExpression": false,
      "displayName": "Folder Path"
    }
  },
  "metadata": {
    "ActivityName": "invoke_async",
    "BindingsVersion": "2.2",
    "DisplayLabel": "FullName"
  }
}
```

**Common Metadata:**
- `ActivityName`: Typically `"invoke_async"`
- `BindingsVersion`: `"2.2"`
- `DisplayLabel`: `"FullName"`

---

### 3. Bucket

Buckets are storage containers for files and data.

**Key Format:** `bucket_name.folder_path`

**Example:**

```json
{
  "resource": "bucket",
  "key": "DocumentStorage.Finance",
  "value": {
    "name": {
      "defaultValue": "DocumentStorage",
      "isExpression": false,
      "displayName": "Name"
    },
    "folderPath": {
      "defaultValue": "Finance",
      "isExpression": false,
      "displayName": "Folder Path"
    }
  },
  "metadata": {
    "ActivityName": "retrieve_async",
    "BindingsVersion": "2.2",
    "DisplayLabel": "FullName"
  }
}
```

**Common Metadata:**
- `ActivityName`: Typically `"retrieve_async"`
- `BindingsVersion`: `"2.2"`
- `DisplayLabel`: `"FullName"`

---

### 4. Index

Indexes are used for search and query operations.

**Key Format:** `index_name.folder_path`

**Example:**

```json
{
  "resource": "index",
  "key": "CustomerIndex.CRM",
  "value": {
    "name": {
      "defaultValue": "CustomerIndex",
      "isExpression": false,
      "displayName": "Name"
    },
    "folderPath": {
      "defaultValue": "CRM",
      "isExpression": false,
      "displayName": "Folder Path"
    }
  },
  "metadata": {
    "ActivityName": "retrieve_async",
    "BindingsVersion": "2.2",
    "DisplayLabel": "FullName"
  }
}
```

**Common Metadata:**
- `ActivityName`: Typically `"retrieve_async"`
- `BindingsVersion`: `"2.2"`
- `DisplayLabel`: `"FullName"`

---
### 5. App

Apps are used to create Human In The Loop tasks and escalations.

**Key Format:** `app_name.app_folder_path`

**Example:**

```json
 {
    "resource": "app",
    "key": "app_name.app_folder_path",
    "value": {
        "name": {
            "defaultValue": "app_name",
            "isExpression": false,
            "displayName": "App Name"
        },
        "folderPath": {
            "defaultValue": "app_folder_path",
            "isExpression": false,
            "displayName": "App Folder Path"
        }
    },
    "metadata": {
        "ActivityName": "create_async",
        "BindingsVersion": "2.2",
        "DisplayLabel": "app_name"
    }
}
```

**Common Metadata:**
- `ActivityName`: Typically `"retrieve_async"`
- `BindingsVersion`: `"2.2"`
- `DisplayLabel`: `"FullName"`

---

### 6. Connection

Connections define external system integrations.

**Key Format:** `connection_key` (no folder path)

**Example:**

```json
{
  "resource": "connection",
  "key": "SalesforceAPI",
  "value": {
    "ConnectionId": {
      "defaultValue": "SalesforceAPI",
      "isExpression": false,
      "displayName": "Connection"
    }
  },
  "metadata": {
    "BindingsVersion": "2.2",
    "Connector": "Salesforce",
    "UseConnectionService": "True"
  }
}
```

**Connection-Specific Metadata:**
- `BindingsVersion`: `"2.2"`
- `Connector`: The type of connector (e.g., `"Salesforce"`, `"SAP"`, `""` for custom)
- `UseConnectionService`: `"True"` or `"False"`

**Note:** Connections do NOT have an `ActivityName` or `DisplayLabel` in metadata.

---

## Value Object Structure

### For Assets, Processes, Buckets, Apps and Indexes

```json
{
  "name": {
    "defaultValue": "resource_name",
    "isExpression": false,
    "displayName": "Name"
  },
  "folderPath": {
    "defaultValue": "folder_path",
    "isExpression": false,
    "displayName": "Folder Path"
  }
}
```

### For Connections

```json
{
  "ConnectionId": {
    "defaultValue": "connection_key",
    "isExpression": false,
    "displayName": "Connection"
  }
}
```

### Property Definition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `defaultValue` | `string` | Yes | The default value for this property |
| `isExpression` | `boolean` | Yes | Whether the value is a dynamic expression (usually `false`) |
| `displayName` | `string` | Yes | Human-readable name shown in UI |

---

## Metadata Object

Metadata provides additional context about the resource binding.

### Common Metadata Fields

| Field | Type | Description | Applicable To |
|-------|------|-------------|---------------|
| `ActivityName` | `string` | Activity used to access the resource | asset, process, bucket, index |
| `BindingsVersion` | `string` | Version of the bindings schema | All resources |
| `DisplayLabel` | `string` | Label format for display | asset, process, bucket, index |
| `Connector` | `string` | Type of connector | connection |
| `UseConnectionService` | `string` | Whether to use connection service | connection |

---

## Complete Example

```json
{
    "$schema": "https://cloud.uipath.com/draft/2024-12/bindings",
    "version": "2.0",
    "resources": [
        {
            "resource": "asset",
            "key": "APIKey.Production",
            "value": {
                "name": {
                    "defaultValue": "APIKey",
                    "isExpression": false,
                    "displayName": "Name"
                },
                "folderPath": {
                    "defaultValue": "Production",
                    "isExpression": false,
                    "displayName": "Folder Path"
                }
            },
            "metadata": {
                "ActivityName": "retrieve_async",
                "BindingsVersion": "2.2",
                "DisplayLabel": "FullName"
            }
        },
        {
            "resource": "process",
            "key": "InvoiceProcessing.Finance",
            "value": {
                "name": {
                    "defaultValue": "InvoiceProcessing",
                    "isExpression": false,
                    "displayName": "Name"
                },
                "folderPath": {
                    "defaultValue": "Finance",
                    "isExpression": false,
                    "displayName": "Folder Path"
                }
            },
            "metadata": {
                "ActivityName": "invoke_async",
                "BindingsVersion": "2.2",
                "DisplayLabel": "FullName"
            }
        },
        {
            "resource": "bucket",
            "key": "InvoiceStorage.Finance",
            "value": {
                "name": {
                    "defaultValue": "InvoiceStorage",
                    "isExpression": false,
                    "displayName": "Name"
                },
                "folderPath": {
                    "defaultValue": "Finance",
                    "isExpression": false,
                    "displayName": "Folder Path"
                }
            },
            "metadata": {
                "ActivityName": "retrieve_async",
                "BindingsVersion": "2.2",
                "DisplayLabel": "FullName"
            }
        },
        {
            "resource": "index",
            "key": "VendorIndex.Finance",
            "value": {
                "name": {
                    "defaultValue": "VendorIndex",
                    "isExpression": false,
                    "displayName": "Name"
                },
                "folderPath": {
                    "defaultValue": "Finance",
                    "isExpression": false,
                    "displayName": "Folder Path"
                }
            },
            "metadata": {
                "ActivityName": "retrieve_async",
                "BindingsVersion": "2.2",
                "DisplayLabel": "FullName"
            }
        },
        {
            "resource": "app",
            "key": "app_name.app_folder_path",
            "value": {
                "name": {
                    "defaultValue": "app_name",
                    "isExpression": false,
                    "displayName": "App Name"
                },
                "folderPath": {
                    "defaultValue": "app_folder_path",
                    "isExpression": false,
                    "displayName": "App Folder Path"
                }
            },
            "metadata": {
                "ActivityName": "create_async",
                "BindingsVersion": "2.2",
                "DisplayLabel": "app_name"
            }
        },
        {
            "resource": "connection",
            "key": "SalesforceAPI",
            "value": {
                "ConnectionId": {
                    "defaultValue": "SalesforceAPI",
                    "isExpression": false,
                    "displayName": "Connection"
                }
            },
            "metadata": {
                "BindingsVersion": "2.2",
                "Connector": "Salesforce",
                "UseConnectionService": "True"
            }
        }
    ]
}
```
---

## JSON Schema Definition

The complete JSON Schema is available in `resources.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://cloud.uipath.com/draft/2024-12/bindings",
  "title": "UiPath Resources Configuration",
  "description": "Configuration file for UiPath resource bindings",
  "type": "object",
  "required": ["version", "resources"],
  "properties": {
    "$schema": {
      "type": "string",
      "description": "Reference to this JSON schema for editor support"
    },
    "version": {
      "type": "string",
      "description": "Configuration version",
      "enum": ["2.0"],
      "default": "2.0"
    },
    "resources": {
      "type": "array",
      "description": "Array of resource bindings",
      "items": { ... }
    }
  }
}
```

See `bindings.schema.json` for the complete definition with all nested structures.

