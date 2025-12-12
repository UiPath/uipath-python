## ResourceCatalogService

Service for searching and discovering UiPath resources across folders.

The Resource Catalog Service provides a centralized way to search and retrieve UiPath resources (assets, queues, processes, storage buckets, etc.) across tenant and folder scopes. It enables programmatic discovery of resources with flexible filtering by resource type, name, and folder location.

See Also

<https://docs.uipath.com/orchestrator/standalone/2024.10/user-guide/about-resource-catalog-service>

Version Availability

This service is available starting from **uipath** version **2.1.168**.

### list

```
list(
    *,
    resource_types=None,
    resource_sub_types=None,
    folder_path=None,
    folder_key=None,
    page_size=_DEFAULT_PAGE_SIZE,
)
```

Get tenant scoped resources and folder scoped resources (accessible to the user).

If no folder identifier is provided (path or key) only tenant resources will be retrieved. This method automatically handles pagination and yields resources one by one.

Parameters:

| Name                 | Type                 | Description                                                       | Default                                         |
| -------------------- | -------------------- | ----------------------------------------------------------------- | ----------------------------------------------- |
| `resource_types`     | \`list[ResourceType] | None\`                                                            | Optional list of resource types to filter by    |
| `resource_sub_types` | \`list[str]          | None\`                                                            | Optional list of resource subtypes to filter by |
| `folder_path`        | \`str                | None\`                                                            | Optional folder path to scope the results       |
| `folder_key`         | \`str                | None\`                                                            | Optional folder key to scope the results        |
| `page_size`          | `int`                | Number of resources to fetch per API call (default: 20, max: 100) | `_DEFAULT_PAGE_SIZE`                            |

Yields:

| Name       | Type       | Description                         |
| ---------- | ---------- | ----------------------------------- |
| `Resource` | `Resource` | Each resource matching the criteria |

Examples:

```
>>> # Get all resources
>>> for resource in uipath.resource_catalog.list():
...     print(f"{resource.name}: {resource.resource_type}")
```

```
>>> # Get specific resource types
>>> assets = list(uipath.resource_catalog.list(
...     resource_types=[ResourceType.ASSET],
... ))
```

```
>>> # Get resources within a specific folder
>>> for resource in uipath.resource_catalog.list(
...     folder_path="/Shared/Finance",
...     resource_types=[ResourceType.ASSET],
...     resource_sub_types=["number"]
... ):
...     print(resource.name)
```

### list_async

```
list_async(
    *,
    resource_types=None,
    resource_sub_types=None,
    folder_path=None,
    folder_key=None,
    page_size=_DEFAULT_PAGE_SIZE,
)
```

Asynchronously get tenant scoped resources and folder scoped resources (accessible to the user).

If no folder identifier is provided (path or key) only tenant resources will be retrieved. This method automatically handles pagination and yields resources one by one.

Parameters:

| Name                 | Type                 | Description                                                       | Default                                         |
| -------------------- | -------------------- | ----------------------------------------------------------------- | ----------------------------------------------- |
| `resource_types`     | \`list[ResourceType] | None\`                                                            | Optional list of resource types to filter by    |
| `resource_sub_types` | \`list[str]          | None\`                                                            | Optional list of resource subtypes to filter by |
| `folder_path`        | \`str                | None\`                                                            | Optional folder path to scope the results       |
| `folder_key`         | \`str                | None\`                                                            | Optional folder key to scope the results        |
| `page_size`          | `int`                | Number of resources to fetch per API call (default: 20, max: 100) | `_DEFAULT_PAGE_SIZE`                            |

Yields:

| Name       | Type                      | Description                         |
| ---------- | ------------------------- | ----------------------------------- |
| `Resource` | `AsyncIterator[Resource]` | Each resource matching the criteria |

Examples:

```
>>> # Get all resources
>>> async for resource in uipath.resource_catalog.list_async():
...     print(f"{resource.name}: {resource.resource_type}")
```

```
>>> # Get specific resource types
>>> assets = []
>>> async for resource in uipath.resource_catalog.list_async(
...     resource_types=[ResourceType.ASSET],
... ):
...     assets.append(resource)
```

```
>>> # Get resources within a specific folder
>>> async for resource in uipath.resource_catalog.list_async(
...     folder_path="/Shared/Finance",
...     resource_types=[ResourceType.ASSET],
...     resource_sub_types=["number"]
... ):
...     print(resource.name)
```

### list_by_type

```
list_by_type(
    *,
    resource_type,
    name=None,
    resource_sub_types=None,
    folder_path=None,
    folder_key=None,
    page_size=_DEFAULT_PAGE_SIZE,
)
```

Get resources of a specific type (tenant scoped or folder scoped).

If no folder identifier is provided (path or key) only tenant resources will be retrieved. This method automatically handles pagination and yields resources one by one.

Parameters:

| Name                 | Type           | Description                                                       | Default                                         |
| -------------------- | -------------- | ----------------------------------------------------------------- | ----------------------------------------------- |
| `resource_type`      | `ResourceType` | The specific resource type to filter by                           | *required*                                      |
| `name`               | \`str          | None\`                                                            | Optional name filter for resources              |
| `resource_sub_types` | \`list[str]    | None\`                                                            | Optional list of resource subtypes to filter by |
| `folder_path`        | \`str          | None\`                                                            | Optional folder path to scope the results       |
| `folder_key`         | \`str          | None\`                                                            | Optional folder key to scope the results        |
| `page_size`          | `int`          | Number of resources to fetch per API call (default: 20, max: 100) | `_DEFAULT_PAGE_SIZE`                            |

Yields:

| Name       | Type       | Description                         |
| ---------- | ---------- | ----------------------------------- |
| `Resource` | `Resource` | Each resource matching the criteria |

Examples:

```
>>> # Get all assets
>>> for resource in uipath.resource_catalog.list_by_type(resource_type=ResourceType.ASSET):
...     print(f"{resource.name}: {resource.resource_sub_type}")
```

```
>>> # Get assets with a specific name pattern
>>> assets = list(uipath.resource_catalog.list_by_type(
...     resource_type=ResourceType.ASSET,
...     name="config"
... ))
```

```
>>> # Get assets within a specific folder with subtype filter
>>> for resource in uipath.resource_catalog.list_by_type(
...     resource_type=ResourceType.ASSET,
...     folder_path="/Shared/Finance",
...     resource_sub_types=["number"]
... ):
...     print(resource.name)
```

### list_by_type_async

```
list_by_type_async(
    *,
    resource_type,
    name=None,
    resource_sub_types=None,
    folder_path=None,
    folder_key=None,
    page_size=_DEFAULT_PAGE_SIZE,
)
```

Asynchronously get resources of a specific type (tenant scoped or folder scoped).

If no folder identifier is provided (path or key) only tenant resources will be retrieved. This method automatically handles pagination and yields resources one by one.

Parameters:

| Name                 | Type           | Description                                                       | Default                                         |
| -------------------- | -------------- | ----------------------------------------------------------------- | ----------------------------------------------- |
| `resource_type`      | `ResourceType` | The specific resource type to filter by                           | *required*                                      |
| `name`               | \`str          | None\`                                                            | Optional name filter for resources              |
| `resource_sub_types` | \`list[str]    | None\`                                                            | Optional list of resource subtypes to filter by |
| `folder_path`        | \`str          | None\`                                                            | Optional folder path to scope the results       |
| `folder_key`         | \`str          | None\`                                                            | Optional folder key to scope the results        |
| `page_size`          | `int`          | Number of resources to fetch per API call (default: 20, max: 100) | `_DEFAULT_PAGE_SIZE`                            |

Yields:

| Name       | Type                      | Description                         |
| ---------- | ------------------------- | ----------------------------------- |
| `Resource` | `AsyncIterator[Resource]` | Each resource matching the criteria |

Examples:

```
>>> # Get all assets asynchronously
>>> async for resource in uipath.resource_catalog.list_by_type_async(resource_type=ResourceType.ASSET):
...     print(f"{resource.name}: {resource.resource_sub_type}")
```

```
>>> # Get assets with a specific name pattern
>>> assets = []
>>> async for resource in uipath.resource_catalog.list_by_type_async(
...     resource_type=ResourceType.ASSET,
...     name="config"
... ):
...     assets.append(resource)
```

```
>>> # Get assets within a specific folder with subtype filter
>>> async for resource in uipath.resource_catalog.list_by_type_async(
...     resource_type=ResourceType.ASSET,
...     folder_path="/Shared/Finance",
...     resource_sub_types=["number"]
... ):
...     print(resource.name)
```

### search

```
search(
    *,
    name=None,
    resource_types=None,
    resource_sub_types=None,
    page_size=_DEFAULT_PAGE_SIZE,
)
```

Search for tenant scoped resources and folder scoped resources (accessible to the user).

This method automatically handles pagination and yields resources one by one.

Parameters:

| Name                 | Type                 | Description                                                       | Default                                         |
| -------------------- | -------------------- | ----------------------------------------------------------------- | ----------------------------------------------- |
| `name`               | \`str                | None\`                                                            | Optional name filter for resources              |
| `resource_types`     | \`list[ResourceType] | None\`                                                            | Optional list of resource types to filter by    |
| `resource_sub_types` | \`list[str]          | None\`                                                            | Optional list of resource subtypes to filter by |
| `page_size`          | `int`                | Number of resources to fetch per API call (default: 20, max: 100) | `_DEFAULT_PAGE_SIZE`                            |

Yields:

| Name       | Type       | Description                                |
| ---------- | ---------- | ------------------------------------------ |
| `Resource` | `Resource` | Each resource matching the search criteria |

Examples:

```
>>> # Search for all resources with "invoice" in the name
>>> for resource in uipath.resource_catalog.search(name="invoice"):
...     print(f"{resource.name}: {resource.resource_type}")
```

```
>>> # Search for specific resource types
>>> for resource in uipath.resource_catalog.search(
...     resource_types=[ResourceType.ASSET]
... ):
...     print(resource.name)
```

### search_async

```
search_async(
    *,
    name=None,
    resource_types=None,
    resource_sub_types=None,
    page_size=_DEFAULT_PAGE_SIZE,
)
```

Asynchronously search for tenant scoped resources and folder scoped resources (accessible to the user).

This method automatically handles pagination and yields resources one by one.

Parameters:

| Name                 | Type                 | Description                                                       | Default                                         |
| -------------------- | -------------------- | ----------------------------------------------------------------- | ----------------------------------------------- |
| `name`               | \`str                | None\`                                                            | Optional name filter for resources              |
| `resource_types`     | \`list[ResourceType] | None\`                                                            | Optional list of resource types to filter by    |
| `resource_sub_types` | \`list[str]          | None\`                                                            | Optional list of resource subtypes to filter by |
| `page_size`          | `int`                | Number of resources to fetch per API call (default: 20, max: 100) | `_DEFAULT_PAGE_SIZE`                            |

Yields:

| Name       | Type                      | Description                                |
| ---------- | ------------------------- | ------------------------------------------ |
| `Resource` | `AsyncIterator[Resource]` | Each resource matching the search criteria |

Examples:

```
>>> # Search for all resources with "invoice" in the name
>>> async for resource in uipath.resource_catalog.search_async(name="invoice"):
...     print(f"{resource.name}: {resource.resource_type}")
```

```
>>> # Search for specific resource types
>>> async for resource in uipath.resource_catalog.search_async(
...     resource_types=[ResourceType.ASSET]
... ):
...     print(resource.name)
```
