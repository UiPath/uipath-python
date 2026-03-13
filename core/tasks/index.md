## TasksService

Service for managing UiPath Action Center tasks.

Tasks are task-based automation components that can be integrated into applications and processes. They represent discrete units of work that can be triggered and monitored through the UiPath API.

This service provides methods to create and retrieve tasks, supporting both app-specific and generic tasks. It inherits folder context management capabilities from FolderContext.

Reference: <https://docs.uipath.com/automation-cloud/docs/actions>

### create

```
create(
    title,
    data=None,
    *,
    app_name=None,
    app_key=None,
    app_folder_path=None,
    app_folder_key=None,
    assignee=None,
    recipient=None,
    priority=None,
    labels=None,
    is_actionable_message_enabled=None,
    actionable_message_metadata=None,
    source_name="Agent",
)
```

Creates a new task synchronously.

This method creates a new action task in UiPath Orchestrator. The action can be either app-specific (using app_name or app_key) or a generic action.

Parameters:

| Name                            | Type             | Description                                                        | Default                                                                                |
| ------------------------------- | ---------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `title`                         | `str`            | The title of the action                                            | *required*                                                                             |
| `data`                          | \`dict[str, Any] | None\`                                                             | Optional dictionary containing input data for the action                               |
| `app_name`                      | \`str            | None\`                                                             | The name of the application (if creating an app-specific action)                       |
| `app_key`                       | \`str            | None\`                                                             | The key of the application (if creating an app-specific action)                        |
| `app_folder_path`               | \`str            | None\`                                                             | Optional folder path for the action                                                    |
| `app_folder_key`                | \`str            | None\`                                                             | Optional folder key for the action                                                     |
| `assignee`                      | \`str            | None\`                                                             | Optional username or email to assign the task to                                       |
| `priority`                      | \`str            | None\`                                                             | Optional priority of the task                                                          |
| `labels`                        | \`list[str]      | None\`                                                             | Optional list of labels for the task                                                   |
| `is_actionable_message_enabled` | \`bool           | None\`                                                             | Optional boolean indicating whether actionable notifications are enabled for this task |
| `actionable_message_metadata`   | \`dict[str, Any] | None\`                                                             | Optional metadata for the action                                                       |
| `source_name`                   | `str`            | The name of the source that created the task. Defaults to 'Agent'. | `'Agent'`                                                                              |

Returns:

| Name     | Type   | Description               |
| -------- | ------ | ------------------------- |
| `Action` | `Task` | The created action object |

Raises:

| Type        | Description                                                          |
| ----------- | -------------------------------------------------------------------- |
| `Exception` | If neither app_name nor app_key is provided for app-specific actions |

### create_async

```
create_async(
    title,
    data=None,
    *,
    app_name=None,
    app_key=None,
    app_folder_path=None,
    app_folder_key=None,
    assignee=None,
    recipient=None,
    priority=None,
    labels=None,
    is_actionable_message_enabled=None,
    actionable_message_metadata=None,
    source_name="Agent",
)
```

Creates a new action asynchronously.

This method creates a new action task in UiPath Orchestrator. The action can be either app-specific (using app_name or app_key) or a generic action.

Parameters:

| Name                            | Type             | Description                                                        | Default                                                                                |
| ------------------------------- | ---------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `title`                         | `str`            | The title of the action                                            | *required*                                                                             |
| `data`                          | \`dict[str, Any] | None\`                                                             | Optional dictionary containing input data for the action                               |
| `app_name`                      | \`str            | None\`                                                             | The name of the application (if creating an app-specific action)                       |
| `app_key`                       | \`str            | None\`                                                             | The key of the application (if creating an app-specific action)                        |
| `app_folder_path`               | \`str            | None\`                                                             | Optional folder path for the action                                                    |
| `app_folder_key`                | \`str            | None\`                                                             | Optional folder key for the action                                                     |
| `assignee`                      | \`str            | None\`                                                             | Optional username or email to assign the task to                                       |
| `priority`                      | \`str            | None\`                                                             | Optional priority of the task                                                          |
| `labels`                        | \`list[str]      | None\`                                                             | Optional list of labels for the task                                                   |
| `is_actionable_message_enabled` | \`bool           | None\`                                                             | Optional boolean indicating whether actionable notifications are enabled for this task |
| `actionable_message_metadata`   | \`dict[str, Any] | None\`                                                             | Optional metadata for the action                                                       |
| `source_name`                   | `str`            | The name of the source that created the task. Defaults to 'Agent'. | `'Agent'`                                                                              |

Returns:

| Name     | Type   | Description               |
| -------- | ------ | ------------------------- |
| `Action` | `Task` | The created action object |

Raises:

| Type        | Description                                                          |
| ----------- | -------------------------------------------------------------------- |
| `Exception` | If neither app_name nor app_key is provided for app-specific actions |

### retrieve

```
retrieve(
    action_key,
    app_folder_path="",
    app_folder_key="",
    app_name=None,
)
```

Retrieves a task by its key synchronously.

Parameters:

| Name              | Type  | Description                                   | Default                             |
| ----------------- | ----- | --------------------------------------------- | ----------------------------------- |
| `action_key`      | `str` | The unique identifier of the task to retrieve | *required*                          |
| `app_folder_path` | `str` | Optional folder path for the task             | `''`                                |
| `app_folder_key`  | `str` | Optional folder key for the task              | `''`                                |
| `app_name`        | \`str | None\`                                        | app name hint for resource override |

Returns: Task: The retrieved task object

### retrieve_async

```
retrieve_async(
    action_key,
    app_folder_path="",
    app_folder_key="",
    app_name=None,
)
```

Retrieves a task by its key asynchronously.

Parameters:

| Name              | Type  | Description                                   | Default                             |
| ----------------- | ----- | --------------------------------------------- | ----------------------------------- |
| `action_key`      | `str` | The unique identifier of the task to retrieve | *required*                          |
| `app_folder_path` | `str` | Optional folder path for the task             | `''`                                |
| `app_folder_key`  | `str` | Optional folder key for the task              | `''`                                |
| `app_name`        | \`str | None\`                                        | app name hint for resource override |

Returns: Task: The retrieved task object
