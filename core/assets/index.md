## AssetsService

Service for managing UiPath assets.

Assets are key-value pairs that can be used to store configuration data, credentials, and other settings used by automation processes.

### list

```
list(
    *,
    folder_path=None,
    folder_key=None,
    filter=None,
    orderby=None,
    skip=0,
    top=100,
)
```

List assets using OData API with offset-based pagination.

Returns a single page of results with pagination metadata.

Parameters:

| Name          | Type  | Description                                     | Default                                                 |
| ------------- | ----- | ----------------------------------------------- | ------------------------------------------------------- |
| `folder_path` | \`str | None\`                                          | Folder path to filter assets.                           |
| `folder_key`  | \`str | None\`                                          | Folder key (mutually exclusive with folder_path).       |
| `filter`      | \`str | None\`                                          | OData $filter expression (e.g., "ValueType eq 'Text'"). |
| `orderby`     | \`str | None\`                                          | OData $orderby expression (e.g., "Name asc").           |
| `skip`        | `int` | Number of items to skip (default 0, max 10000). | `0`                                                     |
| `top`         | `int` | Maximum items per page (default 100, max 1000). | `100`                                                   |

Returns:

| Type                 | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| `PagedResult[Asset]` | PagedResult\[Asset\]: Page of assets with pagination metadata. |

Raises:

| Type         | Description                            |
| ------------ | -------------------------------------- |
| `ValueError` | If skip or top parameters are invalid. |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

# List all assets in the default folder
result = client.assets.list(top=100)
for asset in result.items:
    print(asset.name, asset.value_type)

# List with filter
result = client.assets.list(filter="ValueType eq 'Text'")

# Paginate through all assets
skip = 0
while True:
    result = client.assets.list(skip=skip, top=100)
    for asset in result.items:
        print(asset.name)
    if not result.has_more:
        break
    skip += 100
```

### list_async

```
list_async(
    *,
    folder_path=None,
    folder_key=None,
    filter=None,
    orderby=None,
    skip=0,
    top=100,
)
```

Asynchronously list assets using OData API with offset-based pagination.

Returns a single page of results with pagination metadata.

Parameters:

| Name          | Type  | Description                                     | Default                                                 |
| ------------- | ----- | ----------------------------------------------- | ------------------------------------------------------- |
| `folder_path` | \`str | None\`                                          | Folder path to filter assets.                           |
| `folder_key`  | \`str | None\`                                          | Folder key (mutually exclusive with folder_path).       |
| `filter`      | \`str | None\`                                          | OData $filter expression (e.g., "ValueType eq 'Text'"). |
| `orderby`     | \`str | None\`                                          | OData $orderby expression (e.g., "Name asc").           |
| `skip`        | `int` | Number of items to skip (default 0, max 10000). | `0`                                                     |
| `top`         | `int` | Maximum items per page (default 100, max 1000). | `100`                                                   |

Returns:

| Type                 | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| `PagedResult[Asset]` | PagedResult\[Asset\]: Page of assets with pagination metadata. |

Raises:

| Type         | Description                            |
| ------------ | -------------------------------------- |
| `ValueError` | If skip or top parameters are invalid. |

### retrieve

```
retrieve(name, *, folder_key=None, folder_path=None)
```

Retrieve an asset by its name.

Related Activity: [Get Asset](https://docs.uipath.com/activities/other/latest/workflow/get-robot-asset)

Parameters:

| Name          | Type  | Description            | Default                                                                                           |
| ------------- | ----- | ---------------------- | ------------------------------------------------------------------------------------------------- |
| `name`        | `str` | The name of the asset. | *required*                                                                                        |
| `folder_key`  | \`str | None\`                 | The key of the folder to execute the process in. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                 | The path of the folder to execute the process in. Override the default one set in the SDK config. |

Returns:

| Name        | Type        | Description |
| ----------- | ----------- | ----------- |
| `UserAsset` | \`UserAsset | Asset\`     |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

client.assets.retrieve(name="MyAsset")
```

### retrieve_async

```
retrieve_async(name, *, folder_key=None, folder_path=None)
```

Asynchronously retrieve an asset by its name.

Related Activity: [Get Asset](https://docs.uipath.com/activities/other/latest/workflow/get-robot-asset)

Parameters:

| Name          | Type  | Description            | Default                                                                                           |
| ------------- | ----- | ---------------------- | ------------------------------------------------------------------------------------------------- |
| `name`        | `str` | The name of the asset. | *required*                                                                                        |
| `folder_key`  | \`str | None\`                 | The key of the folder to execute the process in. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                 | The path of the folder to execute the process in. Override the default one set in the SDK config. |

Returns:

| Name        | Type        | Description |
| ----------- | ----------- | ----------- |
| `UserAsset` | \`UserAsset | Asset\`     |

### retrieve_credential

```
retrieve_credential(
    name, *, folder_key=None, folder_path=None
)
```

Gets a specified Orchestrator credential.

The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable)

Related Activity: [Get Credential](https://docs.uipath.com/activities/other/latest/workflow/get-robot-credential)

Parameters:

| Name          | Type  | Description                       | Default                                                                                           |
| ------------- | ----- | --------------------------------- | ------------------------------------------------------------------------------------------------- |
| `name`        | `str` | The name of the credential asset. | *required*                                                                                        |
| `folder_key`  | \`str | None\`                            | The key of the folder to execute the process in. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                            | The path of the folder to execute the process in. Override the default one set in the SDK config. |

Returns:

| Type  | Description |
| ----- | ----------- |
| \`str | None\`      |

Raises:

| Type         | Description                               |
| ------------ | ----------------------------------------- |
| `ValueError` | If the method is called for a user asset. |

### retrieve_credential_async

```
retrieve_credential_async(
    name, *, folder_key=None, folder_path=None
)
```

Asynchronously gets a specified Orchestrator credential.

The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable)

Related Activity: [Get Credential](https://docs.uipath.com/activities/other/latest/workflow/get-robot-credential)

Parameters:

| Name          | Type  | Description                       | Default                                                                                           |
| ------------- | ----- | --------------------------------- | ------------------------------------------------------------------------------------------------- |
| `name`        | `str` | The name of the credential asset. | *required*                                                                                        |
| `folder_key`  | \`str | None\`                            | The key of the folder to execute the process in. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                            | The path of the folder to execute the process in. Override the default one set in the SDK config. |

Returns:

| Type  | Description |
| ----- | ----------- |
| \`str | None\`      |

Raises:

| Type         | Description                               |
| ------------ | ----------------------------------------- |
| `ValueError` | If the method is called for a user asset. |

### update

```
update(robot_asset, *, folder_key=None, folder_path=None)
```

Update an asset's value.

Related Activity: [Set Asset](https://docs.uipath.com/activities/other/latest/workflow/set-asset)

Parameters:

| Name          | Type        | Description                                     | Default    |
| ------------- | ----------- | ----------------------------------------------- | ---------- |
| `robot_asset` | `UserAsset` | The asset object containing the updated values. | *required* |

Returns:

| Name       | Type       | Description                              |
| ---------- | ---------- | ---------------------------------------- |
| `Response` | `Response` | The HTTP response confirming the update. |

Raises:

| Type         | Description                               |
| ------------ | ----------------------------------------- |
| `ValueError` | If the method is called for a user asset. |

### update_async

```
update_async(
    robot_asset, *, folder_key=None, folder_path=None
)
```

Asynchronously update an asset's value.

Related Activity: [Set Asset](https://docs.uipath.com/activities/other/latest/workflow/set-asset)

Parameters:

| Name          | Type        | Description                                     | Default    |
| ------------- | ----------- | ----------------------------------------------- | ---------- |
| `robot_asset` | `UserAsset` | The asset object containing the updated values. | *required* |

Returns:

| Name       | Type       | Description                              |
| ---------- | ---------- | ---------------------------------------- |
| `Response` | `Response` | The HTTP response confirming the update. |
