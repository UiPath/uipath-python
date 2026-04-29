## BucketsService

Service for managing UiPath storage buckets.

Buckets are cloud storage containers that can be used to store and manage files used by automation processes.

### create

```
create(
    name,
    *,
    description=None,
    identifier=None,
    folder_path=None,
    folder_key=None,
)
```

Create a new bucket.

Parameters:

| Name          | Type  | Description                                | Default                                          |
| ------------- | ----- | ------------------------------------------ | ------------------------------------------------ |
| `name`        | `str` | Bucket name (must be unique within folder) | *required*                                       |
| `description` | \`str | None\`                                     | Optional description                             |
| `identifier`  | \`str | None\`                                     | UUID identifier (auto-generated if not provided) |
| `folder_path` | \`str | None\`                                     | Folder to create bucket in                       |
| `folder_key`  | \`str | None\`                                     | Folder key                                       |

Returns:

| Name     | Type     | Description                   |
| -------- | -------- | ----------------------------- |
| `Bucket` | `Bucket` | Newly created bucket resource |

Raises:

| Type        | Description              |
| ----------- | ------------------------ |
| `Exception` | If bucket creation fails |

Examples:

```
>>> bucket = sdk.buckets.create("my-storage")
>>> bucket = sdk.buckets.create(
...     "data-storage",
...     description="Production data"
... )
```

### create_async

```
create_async(
    name,
    *,
    description=None,
    identifier=None,
    folder_path=None,
    folder_key=None,
)
```

Async version of create().

### delete

```
delete(
    *,
    name=None,
    key=None,
    folder_path=None,
    folder_key=None,
)
```

Delete a bucket.

Parameters:

| Name          | Type  | Description | Default                  |
| ------------- | ----- | ----------- | ------------------------ |
| `name`        | \`str | None\`      | Bucket name              |
| `key`         | \`str | None\`      | Bucket identifier (UUID) |
| `folder_path` | \`str | None\`      | Folder path              |
| `folder_key`  | \`str | None\`      | Folder key               |

Raises:

| Type          | Description            |
| ------------- | ---------------------- |
| `LookupError` | If bucket is not found |

Examples:

```
>>> sdk.buckets.delete(name="old-storage")
>>> sdk.buckets.delete(key="abc-123-def")
```

### delete_async

```
delete_async(
    *,
    name=None,
    key=None,
    folder_path=None,
    folder_key=None,
)
```

Async version of delete().

### delete_file

```
delete_file(
    *,
    name=None,
    key=None,
    blob_file_path,
    folder_key=None,
    folder_path=None,
)
```

Delete a file from a bucket.

Parameters:

| Name             | Type  | Description                    | Default           |
| ---------------- | ----- | ------------------------------ | ----------------- |
| `name`           | \`str | None\`                         | Bucket name       |
| `key`            | \`str | None\`                         | Bucket identifier |
| `blob_file_path` | `str` | Path to the file in the bucket | *required*        |
| `folder_key`     | \`str | None\`                         | Folder key        |
| `folder_path`    | \`str | None\`                         | Folder path       |

Examples:

```
>>> sdk.buckets.delete_file(name="my-storage", blob_file_path="data/file.txt")
```

### delete_file_async

```
delete_file_async(
    *,
    name=None,
    key=None,
    blob_file_path,
    folder_key=None,
    folder_path=None,
)
```

Delete a file from a bucket asynchronously.

Parameters:

| Name             | Type  | Description                    | Default           |
| ---------------- | ----- | ------------------------------ | ----------------- |
| `name`           | \`str | None\`                         | Bucket name       |
| `key`            | \`str | None\`                         | Bucket identifier |
| `blob_file_path` | `str` | Path to the file in the bucket | *required*        |
| `folder_key`     | \`str | None\`                         | Folder key        |
| `folder_path`    | \`str | None\`                         | Folder path       |

Examples:

```
>>> await sdk.buckets.delete_file_async(name="my-storage", blob_file_path="data/file.txt")
```

### download

```
download(
    *,
    name=None,
    key=None,
    blob_file_path,
    destination_path,
    folder_key=None,
    folder_path=None,
)
```

Download a file from a bucket.

Parameters:

| Name               | Type  | Description                                  | Default                                          |
| ------------------ | ----- | -------------------------------------------- | ------------------------------------------------ |
| `key`              | \`str | None\`                                       | The key of the bucket.                           |
| `name`             | \`str | None\`                                       | The name of the bucket.                          |
| `blob_file_path`   | `str` | The path to the file in the bucket.          | *required*                                       |
| `destination_path` | `str` | The local path where the file will be saved. | *required*                                       |
| `folder_key`       | \`str | None\`                                       | The key of the folder where the bucket resides.  |
| `folder_path`      | \`str | None\`                                       | The path of the folder where the bucket resides. |

Raises:

| Type         | Description                                        |
| ------------ | -------------------------------------------------- |
| `ValueError` | If neither key nor name is provided.               |
| `Exception`  | If the bucket with the specified key is not found. |

### download_async

```
download_async(
    *,
    name=None,
    key=None,
    blob_file_path,
    destination_path,
    folder_key=None,
    folder_path=None,
)
```

Download a file from a bucket asynchronously.

Parameters:

| Name               | Type  | Description                                  | Default                                          |
| ------------------ | ----- | -------------------------------------------- | ------------------------------------------------ |
| `key`              | \`str | None\`                                       | The key of the bucket.                           |
| `name`             | \`str | None\`                                       | The name of the bucket.                          |
| `blob_file_path`   | `str` | The path to the file in the bucket.          | *required*                                       |
| `destination_path` | `str` | The local path where the file will be saved. | *required*                                       |
| `folder_key`       | \`str | None\`                                       | The key of the folder where the bucket resides.  |
| `folder_path`      | \`str | None\`                                       | The path of the folder where the bucket resides. |

Raises:

| Type         | Description                                        |
| ------------ | -------------------------------------------------- |
| `ValueError` | If neither key nor name is provided.               |
| `Exception`  | If the bucket with the specified key is not found. |

### exists

```
exists(name, *, folder_key=None, folder_path=None)
```

Check if bucket exists.

Parameters:

| Name          | Type  | Description | Default     |
| ------------- | ----- | ----------- | ----------- |
| `name`        | `str` | Bucket name | *required*  |
| `folder_key`  | \`str | None\`      | Folder key  |
| `folder_path` | \`str | None\`      | Folder path |

Returns:

| Name   | Type   | Description           |
| ------ | ------ | --------------------- |
| `bool` | `bool` | True if bucket exists |

Examples:

```
>>> if sdk.buckets.exists("my-storage"):
...     print("Bucket found")
```

### exists_async

```
exists_async(name, *, folder_key=None, folder_path=None)
```

Async version of exists().

### exists_file

```
exists_file(
    *,
    name=None,
    key=None,
    blob_file_path,
    folder_key=None,
    folder_path=None,
)
```

Check if a file exists in a bucket.

Parameters:

| Name             | Type  | Description                                      | Default           |
| ---------------- | ----- | ------------------------------------------------ | ----------------- |
| `name`           | \`str | None\`                                           | Bucket name       |
| `key`            | \`str | None\`                                           | Bucket identifier |
| `blob_file_path` | `str` | Path to the file in the bucket (cannot be empty) | *required*        |
| `folder_key`     | \`str | None\`                                           | Folder key        |
| `folder_path`    | \`str | None\`                                           | Folder path       |

Returns:

| Name   | Type   | Description                          |
| ------ | ------ | ------------------------------------ |
| `bool` | `bool` | True if file exists, False otherwise |

Note

This method uses short-circuit iteration to stop at the first match, making it memory-efficient even for large buckets. It will raise LookupError if the bucket itself doesn't exist.

Raises:

| Type          | Description                                   |
| ------------- | --------------------------------------------- |
| `ValueError`  | If blob_file_path is empty or whitespace-only |
| `LookupError` | If bucket is not found                        |

Examples:

```
>>> if sdk.buckets.exists_file(name="my-storage", blob_file_path="data/file.csv"):
...     print("File exists")
>>> # Check in specific folder
>>> exists = sdk.buckets.exists_file(
...     name="my-storage",
...     blob_file_path="reports/2024/summary.pdf",
...     folder_path="Production"
... )
```

### exists_file_async

```
exists_file_async(
    *,
    name=None,
    key=None,
    blob_file_path,
    folder_key=None,
    folder_path=None,
)
```

Async version of exists_file().

Parameters:

| Name             | Type  | Description                                      | Default           |
| ---------------- | ----- | ------------------------------------------------ | ----------------- |
| `name`           | \`str | None\`                                           | Bucket name       |
| `key`            | \`str | None\`                                           | Bucket identifier |
| `blob_file_path` | `str` | Path to the file in the bucket (cannot be empty) | *required*        |
| `folder_key`     | \`str | None\`                                           | Folder key        |
| `folder_path`    | \`str | None\`                                           | Folder path       |

Returns:

| Name   | Type   | Description                          |
| ------ | ------ | ------------------------------------ |
| `bool` | `bool` | True if file exists, False otherwise |

Raises:

| Type          | Description                                   |
| ------------- | --------------------------------------------- |
| `ValueError`  | If blob_file_path is empty or whitespace-only |
| `LookupError` | If bucket is not found                        |

Examples:

```
>>> if await sdk.buckets.exists_file_async(name="my-storage", blob_file_path="data/file.csv"):
...     print("File exists")
```

### get_files

```
get_files(
    *,
    name=None,
    key=None,
    prefix="",
    recursive=False,
    file_name_glob=None,
    skip=0,
    top=500,
    folder_key=None,
    folder_path=None,
)
```

Get files using OData GetFiles API with offset-based pagination.

This method uses the OData API with $skip/$top for pagination. Supports recursive traversal, glob filtering, and OData features. Automatically excludes directories from results.

Note: Offset-based pagination can degrade performance with very large skip values (e.g., skip > 10000). For sequential iteration over large datasets, consider list_files() instead.

Parameters:

| Name             | Type   | Description                                                          | Default                                          |
| ---------------- | ------ | -------------------------------------------------------------------- | ------------------------------------------------ |
| `name`           | \`str  | None\`                                                               | Bucket name                                      |
| `key`            | \`str  | None\`                                                               | Bucket identifier                                |
| `prefix`         | `str`  | Directory path to filter files (default: root)                       | `''`                                             |
| `recursive`      | `bool` | Recurse subdirectories for flat view (default: False)                | `False`                                          |
| `file_name_glob` | \`str  | None\`                                                               | File filter pattern (e.g., ".pdf", "data\_.csv") |
| `skip`           | `int`  | Number of files to skip (default 0, max 10000). Used for pagination. | `0`                                              |
| `top`            | `int`  | Maximum number of files to return (default 500, max 1000).           | `500`                                            |
| `folder_key`     | \`str  | None\`                                                               | Folder key                                       |
| `folder_path`    | \`str  | None\`                                                               | Folder path                                      |

Returns:

| Type                      | Description                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| `PagedResult[BucketFile]` | PagedResult\[BucketFile\]: Page containing files (directories excluded) and pagination metadata |

Raises:

| Type          | Description                                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| `ValueError`  | If skip < 0, skip > 10000, top < 1, top > 1000, neither name nor key is provided, or file_name_glob is empty |
| `LookupError` | If bucket not found                                                                                          |

Examples:

```
>>> # Get first page
>>> result = sdk.buckets.get_files(name="my-storage")
>>> for file in result.items:
...     print(file.name)
>>>
>>> # Filter with glob pattern
>>> result = sdk.buckets.get_files(
...     name="my-storage",
...     recursive=True,
...     file_name_glob="*.pdf"
... )
>>>
>>> # Manual offset-based pagination
>>> skip = 0
>>> top = 500
>>> all_files = []
>>> while True:
...     result = sdk.buckets.get_files(
...         name="my-storage",
...         prefix="reports/",
...         skip=skip,
...         top=top
...     )
...     all_files.extend(result.items)
...     if not result.has_more:
...         break
...     skip += top
>>>
>>> # Helper function
>>> def iter_all_files_odata(sdk, bucket_name, **filters):
...     skip = 0
...     top = 500
...     while True:
...         result = sdk.buckets.get_files(
...             name=bucket_name,
...             skip=skip,
...             top=top,
...             **filters
...         )
...         yield from result.items
...         if not result.has_more:
...             break
...         skip += top
>>>
>>> # Usage with filters
>>> for file in iter_all_files_odata(
...     sdk,
...     "my-storage",
...     recursive=True,
...     file_name_glob="*.pdf"
... ):
...     process_file(file)
```

Performance

Best for: Filtered queries, random access, sorted results. Consider list_files() for: Sequential iteration over large datasets.

Performance degrades with large skip values due to database offset costs.

### get_files_async

```
get_files_async(
    *,
    name=None,
    key=None,
    prefix="",
    recursive=False,
    file_name_glob=None,
    skip=0,
    top=500,
    folder_key=None,
    folder_path=None,
)
```

Async version of get_files() with offset-based pagination.

Returns a single page of results with pagination metadata. Automatically excludes directories from results.

Parameters:

| Name             | Type   | Description                                               | Default                              |
| ---------------- | ------ | --------------------------------------------------------- | ------------------------------------ |
| `name`           | \`str  | None\`                                                    | Bucket name                          |
| `key`            | \`str  | None\`                                                    | Bucket identifier                    |
| `prefix`         | `str`  | Directory path to filter files                            | `''`                                 |
| `recursive`      | `bool` | Recurse subdirectories for flat view                      | `False`                              |
| `file_name_glob` | \`str  | None\`                                                    | File filter pattern (e.g., "\*.pdf") |
| `skip`           | `int`  | Number of files to skip (default 0, max 10000)            | `0`                                  |
| `top`            | `int`  | Maximum number of files to return (default 500, max 1000) | `500`                                |
| `folder_key`     | \`str  | None\`                                                    | Folder key                           |
| `folder_path`    | \`str  | None\`                                                    | Folder path                          |

Returns:

| Type                      | Description                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| `PagedResult[BucketFile]` | PagedResult\[BucketFile\]: Page containing files (directories excluded) and pagination metadata |

Raises:

| Type          | Description                                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| `ValueError`  | If skip < 0, skip > 10000, top < 1, top > 1000, neither name nor key is provided, or file_name_glob is empty |
| `LookupError` | If bucket not found                                                                                          |

Examples:

```
>>> # Get first page
>>> result = await sdk.buckets.get_files_async(
...     name="my-storage",
...     recursive=True,
...     file_name_glob="*.pdf"
... )
>>> for file in result.items:
...     print(file.name)
>>>
>>> # Manual pagination
>>> skip = 0
>>> top = 500
>>> all_files = []
>>> while True:
...     result = await sdk.buckets.get_files_async(
...         name="my-storage",
...         skip=skip,
...         top=top
...     )
...     all_files.extend(result.items)
...     if not result.has_more:
...         break
...     skip += top
```

### list

```
list(
    *,
    folder_path=None,
    folder_key=None,
    name=None,
    skip=0,
    top=100,
)
```

List buckets using OData API with offset-based pagination.

Returns a single page of results with pagination metadata.

Parameters:

| Name          | Type  | Description                                                 | Default                                          |
| ------------- | ----- | ----------------------------------------------------------- | ------------------------------------------------ |
| `folder_path` | \`str | None\`                                                      | Folder path to filter buckets                    |
| `folder_key`  | \`str | None\`                                                      | Folder key (mutually exclusive with folder_path) |
| `name`        | \`str | None\`                                                      | Filter by bucket name (contains match)           |
| `skip`        | `int` | Number of buckets to skip (default 0, max 10000)            | `0`                                              |
| `top`         | `int` | Maximum number of buckets to return (default 100, max 1000) | `100`                                            |

Returns:

| Type                  | Description                                                            |
| --------------------- | ---------------------------------------------------------------------- |
| `PagedResult[Bucket]` | PagedResult\[Bucket\]: Page containing buckets and pagination metadata |

Raises:

| Type         | Description                                       |
| ------------ | ------------------------------------------------- |
| `ValueError` | If skip < 0, skip > 10000, top < 1, or top > 1000 |

Examples:

```
>>> # Get first page
>>> result = sdk.buckets.list(top=100)
>>> for bucket in result.items:
...     print(bucket.name)
>>>
>>> # Check pagination metadata
>>> if result.has_more:
...     print(f"More results available. Current: skip={result.skip}, top={result.top}")
>>>
>>> # Manual pagination to get all buckets
>>> skip = 0
>>> top = 100
>>> all_buckets = []
>>> while True:
...     result = sdk.buckets.list(skip=skip, top=top, name="invoice")
...     all_buckets.extend(result.items)
...     if not result.has_more:
...         break
...     skip += top
>>>
>>> # Helper function for complete iteration
>>> def iter_all_buckets(sdk, top=100, **filters):
...     skip = 0
...     while True:
...         result = sdk.buckets.list(skip=skip, top=top, **filters)
...         yield from result.items
...         if not result.has_more:
...             break
...         skip += top
>>>
>>> # Usage
>>> for bucket in iter_all_buckets(sdk, name="invoice"):
...     process_bucket(bucket)
```

### list_async

```
list_async(
    *,
    folder_path=None,
    folder_key=None,
    name=None,
    skip=0,
    top=100,
)
```

Async version of list() with offset-based pagination.

Returns a single page of results with pagination metadata.

Parameters:

| Name          | Type  | Description                                                 | Default                                          |
| ------------- | ----- | ----------------------------------------------------------- | ------------------------------------------------ |
| `folder_path` | \`str | None\`                                                      | Folder path to filter buckets                    |
| `folder_key`  | \`str | None\`                                                      | Folder key (mutually exclusive with folder_path) |
| `name`        | \`str | None\`                                                      | Filter by bucket name (contains match)           |
| `skip`        | `int` | Number of buckets to skip (default 0, max 10000)            | `0`                                              |
| `top`         | `int` | Maximum number of buckets to return (default 100, max 1000) | `100`                                            |

Returns:

| Type                  | Description                                                            |
| --------------------- | ---------------------------------------------------------------------- |
| `PagedResult[Bucket]` | PagedResult\[Bucket\]: Page containing buckets and pagination metadata |

Raises:

| Type         | Description                                       |
| ------------ | ------------------------------------------------- |
| `ValueError` | If skip < 0, skip > 10000, top < 1, or top > 1000 |

Examples:

```
>>> # Get first page
>>> result = await sdk.buckets.list_async(top=100)
>>> for bucket in result.items:
...     print(bucket.name)
>>>
>>> # Manual pagination
>>> skip = 0
>>> top = 100
>>> all_buckets = []
>>> while True:
...     result = await sdk.buckets.list_async(skip=skip, top=top)
...     all_buckets.extend(result.items)
...     if not result.has_more:
...         break
...     skip += top
```

### list_files

```
list_files(
    *,
    name=None,
    key=None,
    prefix="",
    take_hint=500,
    continuation_token=None,
    folder_key=None,
    folder_path=None,
)
```

List files in a bucket using cursor-based pagination.

Returns a single page of results with continuation token for manual pagination. This method uses the REST API with continuation tokens for efficient pagination of large file sets. Recommended for sequential iteration over millions of files.

Parameters:

| Name                 | Type  | Description                                                                                                      | Default                                                 |
| -------------------- | ----- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `name`               | \`str | None\`                                                                                                           | Bucket name                                             |
| `key`                | \`str | None\`                                                                                                           | Bucket identifier                                       |
| `prefix`             | `str` | Filter files by prefix                                                                                           | `''`                                                    |
| `take_hint`          | `int` | Minimum number of files to return (default 500, max 1000). The API may return up to 2x this value in some cases. | `500`                                                   |
| `continuation_token` | \`str | None\`                                                                                                           | Token from previous response. Pass None for first page. |
| `folder_key`         | \`str | None\`                                                                                                           | Folder key                                              |
| `folder_path`        | \`str | None\`                                                                                                           | Folder path                                             |

Returns:

| Type                      | Description                                                                      |
| ------------------------- | -------------------------------------------------------------------------------- |
| `PagedResult[BucketFile]` | PagedResult\[BucketFile\]: Page containing files and continuation token metadata |

Raises:

| Type         | Description                            |
| ------------ | -------------------------------------- |
| `ValueError` | If take_hint is not between 1 and 1000 |

Examples:

```
>>> # Get first page
>>> result = sdk.buckets.list_files(name="my-storage")
>>> print(f"Got {len(result.items)} files")
>>>
>>> # Manual pagination to get all files
>>> all_files = []
>>> token = None
>>> while True:
...     result = sdk.buckets.list_files(
...         name="my-storage",
...         prefix="reports/2024/",
...         continuation_token=token
...     )
...     all_files.extend(result.items)
...     if not result.continuation_token:
...         break
...     token = result.continuation_token
>>>
>>> # Helper function for iteration
>>> def iter_all_files(sdk, bucket_name, prefix=""):
...     token = None
...     while True:
...         result = sdk.buckets.list_files(
...             name=bucket_name,
...             prefix=prefix,
...             continuation_token=token
...         )
...         yield from result.items
...         if not result.continuation_token:
...             break
...         token = result.continuation_token
>>>
>>> # Usage
>>> for file in iter_all_files(sdk, "my-storage", "reports/"):
...     print(file.path)
```

Performance

Cursor-based pagination scales efficiently to millions of files. Each page requires one API call regardless of dataset size.

For sequential processing, this is the most efficient method. For filtered queries, consider get_files() with OData filters.

### list_files_async

```
list_files_async(
    *,
    name=None,
    key=None,
    prefix="",
    take_hint=500,
    continuation_token=None,
    folder_key=None,
    folder_path=None,
)
```

Async version of list_files() with cursor-based pagination.

Returns a single page of results with continuation token for manual pagination.

Parameters:

| Name                 | Type  | Description                                                                                                      | Default                                                 |
| -------------------- | ----- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `name`               | \`str | None\`                                                                                                           | Bucket name                                             |
| `key`                | \`str | None\`                                                                                                           | Bucket identifier                                       |
| `prefix`             | `str` | Filter files by prefix                                                                                           | `''`                                                    |
| `take_hint`          | `int` | Minimum number of files to return (default 500, max 1000). The API may return up to 2x this value in some cases. | `500`                                                   |
| `continuation_token` | \`str | None\`                                                                                                           | Token from previous response. Pass None for first page. |
| `folder_key`         | \`str | None\`                                                                                                           | Folder key                                              |
| `folder_path`        | \`str | None\`                                                                                                           | Folder path                                             |

Returns:

| Type                      | Description                                                                      |
| ------------------------- | -------------------------------------------------------------------------------- |
| `PagedResult[BucketFile]` | PagedResult\[BucketFile\]: Page containing files and continuation token metadata |

Raises:

| Type         | Description                            |
| ------------ | -------------------------------------- |
| `ValueError` | If take_hint is not between 1 and 1000 |

Examples:

```
>>> # Get first page
>>> result = await sdk.buckets.list_files_async(name="my-storage")
>>> print(f"Got {len(result.items)} files")
>>>
>>> # Manual pagination
>>> all_files = []
>>> token = None
>>> while True:
...     result = await sdk.buckets.list_files_async(
...         name="my-storage",
...         continuation_token=token
...     )
...     all_files.extend(result.items)
...     if not result.continuation_token:
...         break
...     token = result.continuation_token
```

### retrieve

```
retrieve(
    *,
    name=None,
    key=None,
    folder_key=None,
    folder_path=None,
)
```

Retrieve bucket information by its name.

Parameters:

| Name          | Type  | Description | Default                                          |
| ------------- | ----- | ----------- | ------------------------------------------------ |
| `name`        | \`str | None\`      | The name of the bucket to retrieve.              |
| `key`         | \`str | None\`      | The key of the bucket.                           |
| `folder_key`  | \`str | None\`      | The key of the folder where the bucket resides.  |
| `folder_path` | \`str | None\`      | The path of the folder where the bucket resides. |

Returns:

| Name     | Type     | Description                   |
| -------- | -------- | ----------------------------- |
| `Bucket` | `Bucket` | The bucket resource instance. |

Raises:

| Type         | Description                                         |
| ------------ | --------------------------------------------------- |
| `ValueError` | If neither bucket key nor bucket name is provided.  |
| `Exception`  | If the bucket with the specified name is not found. |

Examples:

```
>>> bucket = sdk.buckets.retrieve(name="my-storage")
>>> print(bucket.name, bucket.identifier)
```

### retrieve_async

```
retrieve_async(
    *,
    name=None,
    key=None,
    folder_key=None,
    folder_path=None,
)
```

Asynchronously retrieve bucket information by its name.

Parameters:

| Name          | Type  | Description | Default                                          |
| ------------- | ----- | ----------- | ------------------------------------------------ |
| `name`        | \`str | None\`      | The name of the bucket to retrieve.              |
| `key`         | \`str | None\`      | The key of the bucket.                           |
| `folder_key`  | \`str | None\`      | The key of the folder where the bucket resides.  |
| `folder_path` | \`str | None\`      | The path of the folder where the bucket resides. |

Returns:

| Name     | Type     | Description                   |
| -------- | -------- | ----------------------------- |
| `Bucket` | `Bucket` | The bucket resource instance. |

Raises:

| Type         | Description                                         |
| ------------ | --------------------------------------------------- |
| `ValueError` | If neither bucket key nor bucket name is provided.  |
| `Exception`  | If the bucket with the specified name is not found. |

Examples:

```
>>> bucket = await sdk.buckets.retrieve_async(name="my-storage")
>>> print(bucket.name, bucket.identifier)
```

### upload

```
upload(
    *,
    key=None,
    name=None,
    blob_file_path,
    content_type=None,
    source_path=None,
    content=None,
    folder_key=None,
    folder_path=None,
)
```

Upload a file to a bucket.

Parameters:

| Name             | Type  | Description                                           | Default                                                                                                         |
| ---------------- | ----- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `key`            | \`str | None\`                                                | The key of the bucket.                                                                                          |
| `name`           | \`str | None\`                                                | The name of the bucket.                                                                                         |
| `blob_file_path` | `str` | The path where the file will be stored in the bucket. | *required*                                                                                                      |
| `content_type`   | \`str | None\`                                                | The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream". |
| `source_path`    | \`str | None\`                                                | The local path of the file to upload.                                                                           |
| `content`        | \`str | bytes                                                 | None\`                                                                                                          |
| `folder_key`     | \`str | None\`                                                | The key of the folder where the bucket resides.                                                                 |
| `folder_path`    | \`str | None\`                                                | The path of the folder where the bucket resides.                                                                |

Raises:

| Type         | Description                                                |
| ------------ | ---------------------------------------------------------- |
| `ValueError` | If neither key nor name is provided.                       |
| `Exception`  | If the bucket with the specified key or name is not found. |

### upload_async

```
upload_async(
    *,
    key=None,
    name=None,
    blob_file_path,
    content_type=None,
    source_path=None,
    content=None,
    folder_key=None,
    folder_path=None,
)
```

Upload a file to a bucket asynchronously.

Parameters:

| Name             | Type  | Description                                           | Default                                                                                                         |
| ---------------- | ----- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `key`            | \`str | None\`                                                | The key of the bucket.                                                                                          |
| `name`           | \`str | None\`                                                | The name of the bucket.                                                                                         |
| `blob_file_path` | `str` | The path where the file will be stored in the bucket. | *required*                                                                                                      |
| `content_type`   | \`str | None\`                                                | The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream". |
| `source_path`    | \`str | None\`                                                | The local path of the file to upload.                                                                           |
| `content`        | \`str | bytes                                                 | None\`                                                                                                          |
| `folder_key`     | \`str | None\`                                                | The key of the folder where the bucket resides.                                                                 |
| `folder_path`    | \`str | None\`                                                | The path of the folder where the bucket resides.                                                                |

Raises:

| Type         | Description                                                |
| ------------ | ---------------------------------------------------------- |
| `ValueError` | If neither key nor name is provided.                       |
| `Exception`  | If the bucket with the specified key or name is not found. |
