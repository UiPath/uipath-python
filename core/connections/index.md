## ConnectionsService

Service for managing UiPath external service connections.

This service provides methods to retrieve direct connection information retrieval and secure token management.

### invoke_activity

```
invoke_activity(
    activity_metadata, connection_id, activity_input
)
```

Invoke an activity synchronously.

Parameters:

| Name                | Type               | Description                                | Default    |
| ------------------- | ------------------ | ------------------------------------------ | ---------- |
| `activity_metadata` | `ActivityMetadata` | Metadata describing the activity to invoke | *required* |
| `connection_id`     | `str`              | The ID of the connection                   | *required* |
| `activity_input`    | `dict[str, Any]`   | Input parameters for the activity          | *required* |

Returns:

| Type  | Description                    |
| ----- | ------------------------------ |
| `Any` | The response from the activity |

Raises:

| Type           | Description                                          |
| -------------- | ---------------------------------------------------- |
| `ValueError`   | If required parameters are missing or invalid        |
| `RuntimeError` | If the HTTP request fails or returns an error status |

### invoke_activity_async

```
invoke_activity_async(
    activity_metadata, connection_id, activity_input
)
```

Invoke an activity asynchronously.

Parameters:

| Name                | Type               | Description                                | Default    |
| ------------------- | ------------------ | ------------------------------------------ | ---------- |
| `activity_metadata` | `ActivityMetadata` | Metadata describing the activity to invoke | *required* |
| `connection_id`     | `str`              | The ID of the connection                   | *required* |
| `activity_input`    | `dict[str, Any]`   | Input parameters for the activity          | *required* |

Returns:

| Type  | Description                    |
| ----- | ------------------------------ |
| `Any` | The response from the activity |

Raises:

| Type           | Description                                          |
| -------------- | ---------------------------------------------------- |
| `ValueError`   | If required parameters are missing or invalid        |
| `RuntimeError` | If the HTTP request fails or returns an error status |

### list

```
list(
    *,
    name=None,
    folder_path=None,
    folder_key=None,
    connector_key=None,
    skip=None,
    top=None,
)
```

Lists all connections with optional filtering.

Parameters:

| Name            | Type  | Description | Default                                                        |
| --------------- | ----- | ----------- | -------------------------------------------------------------- |
| `name`          | \`str | None\`      | Optional connection name to filter (supports partial matching) |
| `folder_path`   | \`str | None\`      | Optional folder path for filtering connections                 |
| `folder_key`    | \`str | None\`      | Optional folder key (mutually exclusive with folder_path)      |
| `connector_key` | \`str | None\`      | Optional connector key to filter by specific connector type    |
| `skip`          | \`int | None\`      | Number of records to skip (for pagination)                     |
| `top`           | \`int | None\`      | Maximum number of records to return                            |

Returns:

| Type               | Description                                      |
| ------------------ | ------------------------------------------------ |
| `list[Connection]` | List\[Connection\]: List of connection instances |

Raises:

| Type         | Description                                                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `ValueError` | If both folder_path and folder_key are provided together, or if folder_path is provided but cannot be resolved to a folder_key |

Examples:

```
>>> # List all connections
>>> connections = sdk.connections.list()
```

```
>>> # Find connections by name
>>> salesforce_conns = sdk.connections.list(name="Salesforce")
```

```
>>> # List all Slack connections in Finance folder
>>> connections = sdk.connections.list(
...     folder_path="Finance",
...     connector_key="uipath-slack"
... )
```

### list_async

```
list_async(
    *,
    name=None,
    folder_path=None,
    folder_key=None,
    connector_key=None,
    skip=None,
    top=None,
)
```

Asynchronously lists all connections with optional filtering.

Parameters:

| Name            | Type  | Description | Default                                                        |
| --------------- | ----- | ----------- | -------------------------------------------------------------- |
| `name`          | \`str | None\`      | Optional connection name to filter (supports partial matching) |
| `folder_path`   | \`str | None\`      | Optional folder path for filtering connections                 |
| `folder_key`    | \`str | None\`      | Optional folder key (mutually exclusive with folder_path)      |
| `connector_key` | \`str | None\`      | Optional connector key to filter by specific connector type    |
| `skip`          | \`int | None\`      | Number of records to skip (for pagination)                     |
| `top`           | \`int | None\`      | Maximum number of records to return                            |

Returns:

| Type               | Description                                      |
| ------------------ | ------------------------------------------------ |
| `list[Connection]` | List\[Connection\]: List of connection instances |

Raises:

| Type         | Description                                                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `ValueError` | If both folder_path and folder_key are provided together, or if folder_path is provided but cannot be resolved to a folder_key |

Examples:

```
>>> # List all connections
>>> connections = await sdk.connections.list_async()
```

```
>>> # Find connections by name
>>> salesforce_conns = await sdk.connections.list_async(name="Salesforce")
```

```
>>> # List all Slack connections in Finance folder
>>> connections = await sdk.connections.list_async(
...     folder_path="Finance",
...     connector_key="uipath-slack"
... )
```

### metadata

```
metadata(
    element_instance_id,
    connector_key,
    tool_path,
    parameters=None,
    schema_mode=True,
    max_jit_depth=5,
)
```

Synchronously retrieve connection API metadata.

This method fetches the metadata for a connection. When parameters are provided, it automatically fetches JIT (Just-In-Time) metadata for cascading fields in a loop, following action URLs up to a maximum depth.

Parameters:

| Name                  | Type             | Description                                                           | Default                                                                                |
| --------------------- | ---------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `element_instance_id` | `int`            | The element instance ID of the connection.                            | *required*                                                                             |
| `connector_key`       | `str`            | The connector key (e.g., 'uipath-atlassian-jira', 'uipath-slack').    | *required*                                                                             |
| `tool_path`           | `str`            | The tool path to retrieve metadata for.                               | *required*                                                                             |
| `parameters`          | \`dict[str, str] | None\`                                                                | Parameter values. When provided, triggers automatic JIT fetching for cascading fields. |
| `schema_mode`         | `bool`           | Whether or not to represent the output schema in the response fields. | `True`                                                                                 |
| `max_jit_depth`       | `int`            | The maximum depth of the JIT resolution loop.                         | `5`                                                                                    |

Returns:

| Name                 | Type                 | Description              |
| -------------------- | -------------------- | ------------------------ |
| `ConnectionMetadata` | `ConnectionMetadata` | The connection metadata. |

Examples:

```
>>> metadata = sdk.connections.metadata(
...     element_instance_id=123,
...     connector_key="uipath-atlassian-jira",
...     tool_path="Issue",
...     parameters={"projectId": "PROJ-123"}  # Optional
... )
```

### metadata_async

```
metadata_async(
    element_instance_id,
    connector_key,
    tool_path,
    parameters=None,
    schema_mode=True,
    max_jit_depth=5,
)
```

Asynchronously retrieve connection API metadata.

This method fetches the metadata for a connection. When parameters are provided, it automatically fetches JIT (Just-In-Time) metadata for cascading fields in a loop, following action URLs up to a maximum depth.

Parameters:

| Name                  | Type             | Description                                                           | Default                                                                                |
| --------------------- | ---------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `element_instance_id` | `int`            | The element instance ID of the connection.                            | *required*                                                                             |
| `connector_key`       | `str`            | The connector key (e.g., 'uipath-atlassian-jira', 'uipath-slack').    | *required*                                                                             |
| `tool_path`           | `str`            | The tool path to retrieve metadata for.                               | *required*                                                                             |
| `parameters`          | \`dict[str, str] | None\`                                                                | Parameter values. When provided, triggers automatic JIT fetching for cascading fields. |
| `schema_mode`         | `bool`           | Whether or not to represent the output schema in the response fields. | `True`                                                                                 |
| `max_jit_depth`       | `int`            | The maximum depth of the JIT resolution loop.                         | `5`                                                                                    |

Returns:

| Name                 | Type                 | Description              |
| -------------------- | -------------------- | ------------------------ |
| `ConnectionMetadata` | `ConnectionMetadata` | The connection metadata. |

Examples:

```
>>> metadata = await sdk.connections.metadata_async(
...     element_instance_id=123,
...     connector_key="uipath-atlassian-jira",
...     tool_path="Issue",
...     parameters={"projectId": "PROJ-123"}  # Optional
... )
```

### retrieve

```
retrieve(key)
```

Retrieve connection details by its key.

This method fetches the configuration and metadata for a connection, which can be used to establish communication with an external service.

Parameters:

| Name  | Type  | Description                                          | Default    |
| ----- | ----- | ---------------------------------------------------- | ---------- |
| `key` | `str` | The unique identifier of the connection to retrieve. | *required* |

Returns:

| Name         | Type         | Description                                                                                |
| ------------ | ------------ | ------------------------------------------------------------------------------------------ |
| `Connection` | `Connection` | The connection details, including configuration parameters and authentication information. |

### retrieve_async

```
retrieve_async(key)
```

Asynchronously retrieve connection details by its key.

This method fetches the configuration and metadata for a connection, which can be used to establish communication with an external service.

Parameters:

| Name  | Type  | Description                                          | Default    |
| ----- | ----- | ---------------------------------------------------- | ---------- |
| `key` | `str` | The unique identifier of the connection to retrieve. | *required* |

Returns:

| Name         | Type         | Description                                                                                |
| ------------ | ------------ | ------------------------------------------------------------------------------------------ |
| `Connection` | `Connection` | The connection details, including configuration parameters and authentication information. |

### retrieve_event_payload

```
retrieve_event_payload(event_args)
```

Retrieve event payload from UiPath Integration Service.

Parameters:

| Name         | Type             | Description                                                       | Default    |
| ------------ | ---------------- | ----------------------------------------------------------------- | ---------- |
| `event_args` | `EventArguments` | The event arguments. Should be passed along from the job's input. | *required* |

Returns:

| Type             | Description                              |
| ---------------- | ---------------------------------------- |
| `dict[str, Any]` | Dict\[str, Any\]: The event payload data |

### retrieve_event_payload_async

```
retrieve_event_payload_async(event_args)
```

Retrieve event payload from UiPath Integration Service.

Parameters:

| Name         | Type             | Description                                                       | Default    |
| ------------ | ---------------- | ----------------------------------------------------------------- | ---------- |
| `event_args` | `EventArguments` | The event arguments. Should be passed along from the job's input. | *required* |

Returns:

| Type             | Description                              |
| ---------------- | ---------------------------------------- |
| `dict[str, Any]` | Dict\[str, Any\]: The event payload data |

### retrieve_token

```
retrieve_token(key, token_type=ConnectionTokenType.DIRECT)
```

Retrieve an authentication token for a connection.

This method obtains a fresh authentication token that can be used to communicate with the external service. This is particularly useful for services that use token-based authentication.

Parameters:

| Name         | Type                  | Description                              | Default    |
| ------------ | --------------------- | ---------------------------------------- | ---------- |
| `key`        | `str`                 | The unique identifier of the connection. | *required* |
| `token_type` | `ConnectionTokenType` | The token type to use.                   | `DIRECT`   |

Returns:

| Name              | Type              | Description                                                                              |
| ----------------- | ----------------- | ---------------------------------------------------------------------------------------- |
| `ConnectionToken` | `ConnectionToken` | The authentication token details, including the token value and any associated metadata. |

### retrieve_token_async

```
retrieve_token_async(
    key, token_type=ConnectionTokenType.DIRECT
)
```

Asynchronously retrieve an authentication token for a connection.

This method obtains a fresh authentication token that can be used to communicate with the external service. This is particularly useful for services that use token-based authentication.

Parameters:

| Name         | Type                  | Description                              | Default    |
| ------------ | --------------------- | ---------------------------------------- | ---------- |
| `key`        | `str`                 | The unique identifier of the connection. | *required* |
| `token_type` | `ConnectionTokenType` | The token type to use.                   | `DIRECT`   |

Returns:

| Name              | Type              | Description                                                                              |
| ----------------- | ----------------- | ---------------------------------------------------------------------------------------- |
| `ConnectionToken` | `ConnectionToken` | The authentication token details, including the token value and any associated metadata. |
