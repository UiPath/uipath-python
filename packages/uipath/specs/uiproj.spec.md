# UiPath Project Configuration Specification

## Overview

The `project.uiproj` file defines project-level metadata for UiPath coded projects. It is used by StudioWeb to identify the project type, name, and description. This file is auto-generated and auto-updated by `uipath init`.

**File Name:** `project.uiproj`

---

## File Structure

```json
{
  "ProjectType": "Agent",
  "Name": "my-project",
  "Description": "Project description",
  "MainFile": null
}
```

---

## Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `ProjectType` | `string` | Yes | The type of project: `"Agent"` or `"Function"` |
| `Name` | `string` | Yes | Project name, taken from `pyproject.toml` `[project].name` |
| `Description` | `string\|null` | No | Project description, taken from `pyproject.toml` `[project].description` |
| `MainFile` | `string\|null` | Yes | Main file path. Required by StudioWeb but not used for coded agents; always `null` for coded projects |

---

## ProjectType

The `ProjectType` is determined automatically from the entrypoints defined in `uipath.json`:

- **`"Agent"`** — when all entrypoints are declared under the `"agents"` key
- **`"Function"`** — when at least one entrypoint is declared under the `"functions"` key, or when no entrypoints exist

If `uipath.json` contains both `"agents"` and `"functions"` (mixed types), a warning is emitted and the type defaults to the first entrypoint's type.

If the project type changes between runs of `uipath init` (e.g., an existing `project.uiproj` has `"Agent"` but the current entrypoints are all functions), a warning is displayed.

---

## Lifecycle

- **Created by:** `uipath init` (when `project.uiproj` does not exist)
- **Updated by:** `uipath init` (when `project.uiproj` already exists)
- **Consumed by:** StudioWeb for project integration

---

## Complete Examples

### Agent Project

```json
{
  "ProjectType": "Agent",
  "Name": "invoice-processor",
  "Description": "An agent that processes invoices using DU",
  "MainFile": null
}
```

### Function Project

```json
{
  "ProjectType": "Function",
  "Name": "calculator",
  "Description": "A simple calculator function",
  "MainFile": null
}
```
