# UiPath Configuration File Specification

## Overview

The `uipath.json` file is a configuration file for UiPath projects that defines runtime behavior, design preferences, packaging options, and Python function entrypoints.

## File Structure

```json
{
  "$schema": "https://cloud.uipath.com/draft/2024-12/uipath",
  "runtimeOptions": { ... },
  "designOptions": { ... },
  "packOptions": { ... },
  "functions": { ... }
}
```

---

## Configuration Sections

### 1. `runtimeOptions`

Controls runtime behavior of your UiPath project.

**Properties:**

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `isConversational` | `boolean` | No | `false` | Enable conversational mode for the runtime |

**Example:**

```json
{
  "runtimeOptions": {
    "isConversational": true
  }
}
```

---

### 2. `designOptions`

Design-time configuration and preferences.

**Example:**

```json
{
  "designOptions": {
  }
}
```

---

### 3. `packOptions`

Controls which files and directories are included or excluded when packaging your project.

**Properties:**

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `fileExtensionsIncluded` | `string[]` | No | `[".py", ".mermaid", ".json", ".yaml", ".yml", ".md"]` | File extensions to include in the package |
| `filesIncluded` | `string[]` | No | `["pyproject.toml"]` | Specific files to always include |
| `filesExcluded` | `string[]` | No | `[]` | Specific files to exclude |
| `directoriesExcluded` | `string[]` | No | `[]` | Directories to exclude from packaging |
| `includeUvLock` | `boolean` | No | `false` | Whether to include `uv.lock` file |

**Example:**

```json
{
  "packOptions": {
    "fileExtensionsIncluded": [".py", ".yaml", ".md"],
    "filesIncluded": ["pyproject.toml"],
    "filesExcluded": ["secret.env"],
    "directoriesExcluded": ["tests", "venv"],
    "includeUvLock": true
  }
}
```

---

### 4. `functions`

Defines entrypoints for pure Python scripts. Each key is a friendly name for the entrypoint, and each value specifies the file path and function name.

**Format:**

```
"entrypoint_name": "path/to/file.py:function_name"
```

**Properties:**

- Keys: Any string (entrypoint name)
- Values: String in format `file_path:function_name`

**Example:**

```json
{
  "functions": {
    "main": "src/main.py:main",
    "process": "src/graph.py:run",
    "generateReport": "src/reporting.py:generate_report",
    "cleanup": "scripts/cleanup.py:cleanup_resources"
  }
}
```

**Rules:**

- File paths are relative to the project root
- Function names must match the actual Python function name
- The colon (`:`) separates the file path from the function name

---

## Complete Example

```json
{
  "$schema": "https://cloud.uipath.com/draft/2024-12/uipath",
  "runtimeOptions": {
    "isConversational": false
  },
  "designOptions": {},
  "packOptions": {
    "fileExtensionsIncluded": [".py", ".json", ".yaml", ".md"],
    "filesIncluded": ["pyproject.toml", "README.md"],
    "filesExcluded": ["secret.env", ".env.local"],
    "directoriesExcluded": ["venv"],
    "includeUvLock": true
  },
  "functions": {
    "main": "src/main.py:main",
    "process": "src/graph.py:run",
    "generateReport": "src/reporting.py:generate_report"
  }
}
```

---

## Python Integration

### Loading Configuration with Defaults

```python
import json
from pathlib import Path

def load_config(config_path="uipath.json"):
    """Load uipath.json with sensible defaults if file doesn't exist."""

    # Default configuration
    default_config = {
        "runtimeOptions": {
            "isConversational": False
        },
        "designOptions": {},
        "packOptions": {
            "fileExtensionsIncluded": [".py", ".mermaid", ".json", ".yaml", ".yml", ".md"],
            "filesIncluded": ["pyproject.toml"],
            "filesExcluded": [],
            "directoriesExcluded": [],
            "includeUvLock": False
        },
        "functions": {}
    }

    # Try to load user's config
    config_file = Path(config_path)
    if not config_file.exists():
        return default_config

    try:
        with open(config_file, 'r') as f:
            user_config = json.load(f)

        # Merge with defaults (user config takes precedence)
        config = default_config.copy()
        for key in user_config:
            if key in config and isinstance(config[key], dict):
                config[key].update(user_config[key])
            else:
                config[key] = user_config[key]

        return config

    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in {config_path}: {e}")
        return default_config
```

---

## JSON Schema Definition

The complete JSON Schema is available in `uipath.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://cloud.uipath.com/draft/2024-12/uipath",
  "title": "UiPath Configuration",
  "description": "Configuration file for UiPath projects",
  "type": "object",
  "properties": {
    "$schema": {
      "type": "string",
      "description": "Reference to this JSON schema for editor support"
    },
    "runtimeOptions": {
      "type": "object",
      "description": "Runtime behavior configuration",
      "properties": {
        "isConversational": {
          "type": "boolean",
          "description": "Enable conversational mode for the runtime",
          "default": false
        }
      },
      "additionalProperties": true
    },
    "designOptions": {
      "type": "object",
      "description": "Design-time configuration and preferences",
      "additionalProperties": true
    },
    "packOptions": {
      "type": "object",
      "description": "File inclusion and exclusion settings for packaging",
      "properties": {
        "fileExtensionsIncluded": {
          "type": "array",
          "description": "File extensions to include in the package",
          "items": {
            "type": "string",
            "pattern": "^\\."
          },
          "default": [".py", ".mermaid", ".json", ".yaml", ".yml", ".md"]
        },
        "filesIncluded": {
          "type": "array",
          "description": "Specific files to include in the package",
          "items": {
            "type": "string"
          },
          "default": ["pyproject.toml"]
        },
        "filesExcluded": {
          "type": "array",
          "description": "Specific files to exclude from the package",
          "items": {
            "type": "string"
          },
          "default": []
        },
        "directoriesExcluded": {
          "type": "array",
          "description": "Directories to exclude from the package",
          "items": {
            "type": "string"
          },
          "default": []
        },
        "includeUvLock": {
          "type": "boolean",
          "description": "Whether to include uv.lock file in the package",
          "default": false
        }
      },
      "additionalProperties": false
    },
    "functions": {
      "type": "object",
      "description": "Entrypoint definitions for pure Python scripts. Each key is an entrypoint name, and each value is a path in format 'file_path:function_name'",
      "additionalProperties": {
        "type": "string"
      }
    }
  },
  "additionalProperties": false
}
```
