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
7. **Property** - Connector-defined resource properties (e.g. SharePoint folder IDs selected at design time)


---

## Resource Structure

Each resource in the `resources` array has the following structure:

```json
{
  "resource": "asset|process|bucket|index|connection|Property",
  "key": "unique_key",
  "value": { ... },
  "metadata": { ... }
}
```

### Common Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `resource` | `string` | Yes | Resource type (one of the seven types) |
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

### 7. Property

Property bindings represent connector-defined resources that a user browses and selects at design time (e.g. a SharePoint folder, an OneDrive file). They are child resources of a parent Connection binding and contain **arbitrary sub-properties** with resolved values.

**Key Format:** `<parent-connection-uuid>.<label>`

**Example:**

```json
{
  "resource": "Property",
  "key": "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder",
  "value": {
    "FullName": {
      "defaultValue": "Invoices",
      "isExpression": false,
      "displayName": "File or folder",
      "description": "Select a file or folder",
      "propertyName": "BrowserItemFriendlyName"
    },
    "ID": {
      "defaultValue": "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M",
      "isExpression": false,
      "displayName": "File or folder",
      "description": "The file or folder of interest",
      "propertyName": "BrowserItemId"
    },
    "ParentDriveID": {
      "defaultValue": "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt",
      "isExpression": false,
      "displayName": "Drive",
      "description": "The drive (OneDrive/SharePoint) of file or folder",
      "propertyName": "BrowserDriveId"
    }
  },
  "metadata": {
    "ActivityName": "SharePoint Invoices folder",
    "BindingsVersion": "2.1",
    "ObjectName": "CuratedFile",
    "DisplayLabel": "FullName",
    "ParentResourceKey": "Connection.775694d9-4c5b-430f-bf47-6079b0ce8623"
  }
}
```

**Property-Specific Metadata:**
- `ParentResourceKey`: The key of the parent Connection resource (`"Connection.<uuid>"`)
- `ObjectName`: The connector-defined object type (e.g. `"CuratedFile"`)
- `DisplayLabel`: The sub-property used as the primary display value

---

## Using Bindings at Runtime

The `BindingsService` allows users to dynamically query resources configured at design time (and overwritten at runtime) directly from `bindings.json`. You can access any binding resource type (Properties, assets, queues, etc.) by passing its key.

**Querying Connector `Property` Bindings:**
```python
from uipath import UiPath
sdk = UiPath()

# Get a single sub-property value
folder_id = sdk.bindings.get_property(
    "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder", 
    "ID"
) # → "017NI543..."

# You can also use just a suffix of the key:
folder_id = sdk.bindings.get_property("SharePoint Invoices folder", "ID")

# Get all sub-properties as a dict
props = sdk.bindings.get_property("SharePoint Invoices folder")
# → {"FullName": "Invoices", "ID": "017NI543...", "ParentDriveID": "b!fFiPz..."}
```

**Querying Standard Bindings (Assets, Buckets, etc.):**
```python
from uipath import UiPath
sdk = UiPath()

# For a specific sub-property
asset_folder_path = sdk.bindings.get_property("DatabaseConnectionString.Production", "folderPath")
# → "Production"

# Get all sub-properties
asset_props = sdk.bindings.get_property("DatabaseConnectionString.Production")
# → {'name': 'DatabaseConnectionString', 'folderPath': 'Production'}
```

---

## Value Object Structure

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

### For Property bindings

The keys and number of sub-properties are connector-defined and vary by connector activity. Each sub-property follows this structure:

```json
{
  "<SubPropertyName>": {
    "defaultValue": "resolved_value",
    "isExpression": false,
    "displayName": "Human-readable label",
    "description": "Optional longer description",
    "propertyName": "ConnectorInternalPropertyName"
  }
}
```

### Sub-property Definition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `defaultValue` | `string` | Yes | The resolved value for this sub-property |
| `isExpression` | `boolean` | Yes | Whether the value is a dynamic expression (usually `false`) |
| `displayName` | `string` | Yes | Human-readable name shown in UI |
| `description` | `string` | No | Optional longer description of the sub-property |
| `propertyName` | `string` | No | Internal connector property name |

---

## Metadata Object

Metadata provides additional context about the resource binding.

### Common Metadata Fields

| Field | Type | Description | Applicable To |
|-------|------|-------------|---------------|
| `ActivityName` | `string` | Activity used to access the resource | asset, process, bucket, index, Property |
| `BindingsVersion` | `string` | Version of the bindings schema | All resources |
| `DisplayLabel` | `string` | Label format for display | asset, process, bucket, index, Property |
| `Connector` | `string` | Type of connector | connection |
| `UseConnectionService` | `string` | Whether to use connection service | connection |
| `ObjectName` | `string` | Connector-defined object type | Property |
| `ParentResourceKey` | `string` | Key of the parent Connection resource (`"Connection.<uuid>"`) | Property |

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
        },
        {
            "resource": "Property",
            "key": "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder",
            "value": {
                "FullName": {
                    "defaultValue": "Invoices",
                    "isExpression": false,
                    "displayName": "File or folder",
                    "description": "Select a file or folder",
                    "propertyName": "BrowserItemFriendlyName"
                },
                "ID": {
                    "defaultValue": "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M",
                    "isExpression": false,
                    "displayName": "File or folder",
                    "description": "The file or folder of interest",
                    "propertyName": "BrowserItemId"
                },
                "ParentDriveID": {
                    "defaultValue": "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt",
                    "isExpression": false,
                    "displayName": "Drive",
                    "description": "The drive (OneDrive/SharePoint) of file or folder",
                    "propertyName": "BrowserDriveId"
                }
            },
            "metadata": {
                "ActivityName": "SharePoint Invoices folder",
                "BindingsVersion": "2.1",
                "ObjectName": "CuratedFile",
                "DisplayLabel": "FullName",
                "ParentResourceKey": "Connection.775694d9-4c5b-430f-bf47-6079b0ce8623"
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

