# UiPath Entrypoints Configuration Specification

## Overview

The `entry-points.json` file defines entry points for UiPath projects with their input and output schemas. Each entry point represents a callable function, workflow or agent with a well-defined contract specified using JSON Schema.

**File Name:** `entry-points.json`

---

## File Structure

```json
{
  "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
  "entryPoints": [
    { ... },
    { ... }
  ]
}
```

---

## Top-Level Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `$schema` | `string` | Yes | Schema URI for validation and IDE support |
| `$id` | `string` | Yes | Identifier for this configuration file |
| `entryPoints` | `array` | Yes | Array of entry point definitions |

### Standard Values

- **`$schema`**: `"https://cloud.uipath.com/draft/2024-12/entry-point"`

---

## Entry Point Structure

Each entry point in the `entryPoints` array defines a callable endpoint with input/output contracts.

### Entry Point Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uniqueId` | `string` | Yes | UUID v4 identifier for this entry point |
| `filePath` | `string` | Yes | Relative path to the file containing this entry point |
| `type` | `string` | Yes | Type of entry point (e.g., `"agent"`, `"workflow"`, `"function"`) |
| `displayName` | `string` | No | Human-readable name (max 1024 characters) |
| `input` | `object\|null` | No | JSON Schema defining input parameters |
| `output` | `object\|null` | No | JSON Schema defining output structure |

---

## Entry Point Types

Common entry point types include:

- **`agent`** - Agentic workflow
- **`process`** - Standard workflow process
- **`function`** - Pure function or utility

---

## Input/Output Schemas

Both `input` and `output` use **JSON Schema (Draft 7)** to define their structure.

### Schema Structure

```json
{
  "type": "object",
  "properties": {
    "propertyName": {
      "type": "string|number|boolean|object|array",
      "description": "Property description",
      // Additional JSON Schema keywords
    }
  },
  "required": ["propertyName"]
}
```

### Supported Types

- `string` - Text values
- `number` - Numeric values (integer or float)
- `integer` - Integer values only
- `boolean` - True/false values
- `object` - Nested objects
- `array` - Lists of items
- `null` - Null value

### Common Schema Keywords

| Keyword | Applicable To | Description |
|---------|---------------|-------------|
| `type` | All | Data type |
| `description` | All | Human-readable description |
| `default` | All | Default value |
| `enum` | All | Allowed values |
| `required` | object | Required property names |
| `properties` | object | Object property definitions |
| `items` | array | Array item schema |
| `minimum` / `maximum` | number | Numeric bounds |
| `minLength` / `maxLength` | string | String length constraints |
| `pattern` | string | Regex pattern |
| `format` | string | String format (e.g., `"email"`, `"date-time"`) |

---

## Complete Example

### Simple Calculator Agent

```json
{
  "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
  "entryPoints": [
    {
      "filePath": "main.py",
      "uniqueId": "03934894-5380-46d7-950c-b4d468111125",
      "type": "agent",
      "displayName": "Calculator Agent",
      "input": {
        "type": "object",
        "properties": {
          "a": {
            "type": "number",
            "description": "First operand"
          },
          "b": {
            "type": "number",
            "description": "Second operand"
          },
          "operator": {
            "type": "string",
            "enum": ["+", "-", "*", "/", "random"],
            "description": "Mathematical operation to perform"
          }
        },
        "required": ["a", "b", "operator"]
      },
      "output": {
        "type": "object",
        "properties": {
          "result": {
            "type": "number",
            "description": "Calculation result"
          }
        },
        "required": ["result"]
      }
    }
  ]
}
```
