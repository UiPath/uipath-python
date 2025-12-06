## ContextGroundingService

Service for managing semantic automation contexts in UiPath.

Context Grounding is a feature that helps in understanding and managing the semantic context in which automation processes operate. It provides capabilities for indexing, retrieving, and searching through contextual information that can be used to enhance AI-enabled automation.

This service requires a valid folder key to be set in the environment, as context grounding operations are always performed within a specific folder context.

### add_to_index

```
add_to_index(
    name,
    blob_file_path,
    content_type=None,
    content=None,
    source_path=None,
    folder_key=None,
    folder_path=None,
    ingest_data=True,
)
```

Add content to the index.

Parameters:

| Name             | Type   | Description                                                                      | Default                                                                                                         |
| ---------------- | ------ | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `name`           | `str`  | The name of the index to add content to.                                         | *required*                                                                                                      |
| `content_type`   | \`str  | None\`                                                                           | The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream". |
| `blob_file_path` | `str`  | The path where the blob will be stored in the storage bucket.                    | *required*                                                                                                      |
| `content`        | \`str  | bytes                                                                            | None\`                                                                                                          |
| `source_path`    | \`str  | None\`                                                                           | The source path of the content if it is being uploaded from a file.                                             |
| `folder_key`     | \`str  | None\`                                                                           | The key of the folder where the index resides.                                                                  |
| `folder_path`    | \`str  | None\`                                                                           | The path of the folder where the index resides.                                                                 |
| `ingest_data`    | `bool` | Whether to ingest data in the index after content is uploaded. Defaults to True. | `True`                                                                                                          |

Raises:

| Type         | Description                                                              |
| ------------ | ------------------------------------------------------------------------ |
| `ValueError` | If neither content nor source_path is provided, or if both are provided. |

### add_to_index_async

```
add_to_index_async(
    name,
    blob_file_path,
    content_type=None,
    content=None,
    source_path=None,
    folder_key=None,
    folder_path=None,
    ingest_data=True,
)
```

Asynchronously add content to the index.

Parameters:

| Name             | Type   | Description                                                                      | Default                                                                                                         |
| ---------------- | ------ | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `name`           | `str`  | The name of the index to add content to.                                         | *required*                                                                                                      |
| `content_type`   | \`str  | None\`                                                                           | The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream". |
| `blob_file_path` | `str`  | The path where the blob will be stored in the storage bucket.                    | *required*                                                                                                      |
| `content`        | \`str  | bytes                                                                            | None\`                                                                                                          |
| `source_path`    | \`str  | None\`                                                                           | The source path of the content if it is being uploaded from a file.                                             |
| `folder_key`     | \`str  | None\`                                                                           | The key of the folder where the index resides.                                                                  |
| `folder_path`    | \`str  | None\`                                                                           | The path of the folder where the index resides.                                                                 |
| `ingest_data`    | `bool` | Whether to ingest data in the index after content is uploaded. Defaults to True. | `True`                                                                                                          |

Raises:

| Type         | Description                                                              |
| ------------ | ------------------------------------------------------------------------ |
| `ValueError` | If neither content nor source_path is provided, or if both are provided. |

### create_index

```
create_index(
    name,
    source,
    description=None,
    advanced_ingestion=True,
    preprocessing_request=LLMV4_REQUEST,
    folder_key=None,
    folder_path=None,
)
```

Create a new context grounding index.

Parameters:

| Name                    | Type           | Description                                                                                                                                                                                                                                                                                                                                                                                     | Default                                                              |
| ----------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `name`                  | `str`          | The name of the index to create.                                                                                                                                                                                                                                                                                                                                                                | *required*                                                           |
| `source`                | `SourceConfig` | Source configuration using one of: - BucketSourceConfig: For storage buckets - GoogleDriveSourceConfig: For Google Drive - DropboxSourceConfig: For Dropbox - OneDriveSourceConfig: For OneDrive - ConfluenceSourceConfig: For Confluence The source can include an optional indexer field for scheduled indexing: source.indexer = Indexer(cron_expression="0 0 18 ? * 2", time_zone_id="UTC") | *required*                                                           |
| `description`           | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | Description of the index.                                            |
| `advanced_ingestion`    | \`bool         | None\`                                                                                                                                                                                                                                                                                                                                                                                          | Enable advanced ingestion with preprocessing. Defaults to True.      |
| `preprocessing_request` | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | The OData type for preprocessing request. Defaults to LLMV4_REQUEST. |
| `folder_key`            | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | The key of the folder where the index will be created.               |
| `folder_path`           | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | The path of the folder where the index will be created.              |

Returns:

| Name                    | Type                    | Description                    |
| ----------------------- | ----------------------- | ------------------------------ |
| `ContextGroundingIndex` | `ContextGroundingIndex` | The created index information. |

### create_index_async

```
create_index_async(
    name,
    source,
    description=None,
    advanced_ingestion=True,
    preprocessing_request=LLMV4_REQUEST,
    folder_key=None,
    folder_path=None,
)
```

Create a new context grounding index.

Parameters:

| Name                    | Type           | Description                                                                                                                                                                                                                                                                                                                                                                                     | Default                                                              |
| ----------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `name`                  | `str`          | The name of the index to create.                                                                                                                                                                                                                                                                                                                                                                | *required*                                                           |
| `source`                | `SourceConfig` | Source configuration using one of: - BucketSourceConfig: For storage buckets - GoogleDriveSourceConfig: For Google Drive - DropboxSourceConfig: For Dropbox - OneDriveSourceConfig: For OneDrive - ConfluenceSourceConfig: For Confluence The source can include an optional indexer field for scheduled indexing: source.indexer = Indexer(cron_expression="0 0 18 ? * 2", time_zone_id="UTC") | *required*                                                           |
| `description`           | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | Description of the index.                                            |
| `advanced_ingestion`    | \`bool         | None\`                                                                                                                                                                                                                                                                                                                                                                                          | Enable advanced ingestion with preprocessing. Defaults to True.      |
| `preprocessing_request` | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | The OData type for preprocessing request. Defaults to LLMV4_REQUEST. |
| `folder_key`            | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | The key of the folder where the index will be created.               |
| `folder_path`           | \`str          | None\`                                                                                                                                                                                                                                                                                                                                                                                          | The path of the folder where the index will be created.              |

Returns:

| Name                    | Type                    | Description                    |
| ----------------------- | ----------------------- | ------------------------------ |
| `ContextGroundingIndex` | `ContextGroundingIndex` | The created index information. |

### delete_index

```
delete_index(index, folder_key=None, folder_path=None)
```

Delete a context grounding index.

This method removes the specified context grounding index from Orchestrator.

Parameters:

| Name          | Type                    | Description                            | Default                                         |
| ------------- | ----------------------- | -------------------------------------- | ----------------------------------------------- |
| `index`       | `ContextGroundingIndex` | The context grounding index to delete. | *required*                                      |
| `folder_key`  | \`str                   | None\`                                 | The key of the folder where the index resides.  |
| `folder_path` | \`str                   | None\`                                 | The path of the folder where the index resides. |

### delete_index_async

```
delete_index_async(
    index, folder_key=None, folder_path=None
)
```

Asynchronously delete a context grounding index.

This method removes the specified context grounding index from Orchestrator.

Parameters:

| Name          | Type                    | Description                            | Default                                         |
| ------------- | ----------------------- | -------------------------------------- | ----------------------------------------------- |
| `index`       | `ContextGroundingIndex` | The context grounding index to delete. | *required*                                      |
| `folder_key`  | \`str                   | None\`                                 | The key of the folder where the index resides.  |
| `folder_path` | \`str                   | None\`                                 | The path of the folder where the index resides. |

### ingest_data

```
ingest_data(index, folder_key=None, folder_path=None)
```

Ingest data into the context grounding index.

Parameters:

| Name          | Type                    | Description                                            | Default                                         |
| ------------- | ----------------------- | ------------------------------------------------------ | ----------------------------------------------- |
| `index`       | `ContextGroundingIndex` | The context grounding index to perform data ingestion. | *required*                                      |
| `folder_key`  | \`str                   | None\`                                                 | The key of the folder where the index resides.  |
| `folder_path` | \`str                   | None\`                                                 | The path of the folder where the index resides. |

### ingest_data_async

```
ingest_data_async(index, folder_key=None, folder_path=None)
```

Asynchronously ingest data into the context grounding index.

Parameters:

| Name          | Type                    | Description                                            | Default                                         |
| ------------- | ----------------------- | ------------------------------------------------------ | ----------------------------------------------- |
| `index`       | `ContextGroundingIndex` | The context grounding index to perform data ingestion. | *required*                                      |
| `folder_key`  | \`str                   | None\`                                                 | The key of the folder where the index resides.  |
| `folder_path` | \`str                   | None\`                                                 | The path of the folder where the index resides. |

### retrieve

```
retrieve(name, folder_key=None, folder_path=None)
```

Retrieve context grounding index information by its name.

Parameters:

| Name          | Type  | Description                                | Default                                         |
| ------------- | ----- | ------------------------------------------ | ----------------------------------------------- |
| `name`        | `str` | The name of the context index to retrieve. | *required*                                      |
| `folder_key`  | \`str | None\`                                     | The key of the folder where the index resides.  |
| `folder_path` | \`str | None\`                                     | The path of the folder where the index resides. |

Returns:

| Name                    | Type                    | Description                                                               |
| ----------------------- | ----------------------- | ------------------------------------------------------------------------- |
| `ContextGroundingIndex` | `ContextGroundingIndex` | The index information, including its configuration and metadata if found. |

Raises:

| Type        | Description                               |
| ----------- | ----------------------------------------- |
| `Exception` | If no index with the given name is found. |

### retrieve_async

```
retrieve_async(name, folder_key=None, folder_path=None)
```

Asynchronously retrieve context grounding index information by its name.

Parameters:

| Name          | Type  | Description                                | Default                                         |
| ------------- | ----- | ------------------------------------------ | ----------------------------------------------- |
| `name`        | `str` | The name of the context index to retrieve. | *required*                                      |
| `folder_key`  | \`str | None\`                                     | The key of the folder where the index resides.  |
| `folder_path` | \`str | None\`                                     | The path of the folder where the index resides. |

Returns:

| Name                    | Type                    | Description                                                               |
| ----------------------- | ----------------------- | ------------------------------------------------------------------------- |
| `ContextGroundingIndex` | `ContextGroundingIndex` | The index information, including its configuration and metadata if found. |

Raises:

| Type        | Description                               |
| ----------- | ----------------------------------------- |
| `Exception` | If no index with the given name is found. |

### retrieve_by_id

```
retrieve_by_id(id, folder_key=None, folder_path=None)
```

Retrieve context grounding index information by its ID.

This method provides direct access to a context index using its unique identifier, which can be more efficient than searching by name.

Parameters:

| Name          | Type  | Description                                 | Default                                         |
| ------------- | ----- | ------------------------------------------- | ----------------------------------------------- |
| `id`          | `str` | The unique identifier of the context index. | *required*                                      |
| `folder_key`  | \`str | None\`                                      | The key of the folder where the index resides.  |
| `folder_path` | \`str | None\`                                      | The path of the folder where the index resides. |

Returns:

| Name  | Type  | Description                                                      |
| ----- | ----- | ---------------------------------------------------------------- |
| `Any` | `Any` | The index information, including its configuration and metadata. |

### retrieve_by_id_async

```
retrieve_by_id_async(id, folder_key=None, folder_path=None)
```

Retrieve asynchronously context grounding index information by its ID.

This method provides direct access to a context index using its unique identifier, which can be more efficient than searching by name.

Parameters:

| Name          | Type  | Description                                 | Default                                         |
| ------------- | ----- | ------------------------------------------- | ----------------------------------------------- |
| `id`          | `str` | The unique identifier of the context index. | *required*                                      |
| `folder_key`  | \`str | None\`                                      | The key of the folder where the index resides.  |
| `folder_path` | \`str | None\`                                      | The path of the folder where the index resides. |

Returns:

| Name  | Type  | Description                                                      |
| ----- | ----- | ---------------------------------------------------------------- |
| `Any` | `Any` | The index information, including its configuration and metadata. |

### retrieve_deep_rag

```
retrieve_deep_rag(id, *, index_name=None)
```

Retrieves a Deep RAG task.

Parameters:

| Name         | Type  | Description                  | Default                                |
| ------------ | ----- | ---------------------------- | -------------------------------------- |
| `id`         | `str` | The id of the Deep RAG task. | *required*                             |
| `index_name` | \`str | None\`                       | Index name hint for resource override. |

Returns:

| Name              | Type              | Description                 |
| ----------------- | ----------------- | --------------------------- |
| `DeepRagResponse` | `DeepRagResponse` | The Deep RAG task response. |

### retrieve_deep_rag_async

```
retrieve_deep_rag_async(id, *, index_name=None)
```

Asynchronously retrieves a Deep RAG task.

Parameters:

| Name         | Type  | Description                  | Default                                |
| ------------ | ----- | ---------------------------- | -------------------------------------- |
| `id`         | `str` | The id of the Deep RAG task. | *required*                             |
| `index_name` | \`str | None\`                       | Index name hint for resource override. |

Returns:

| Name              | Type              | Description                 |
| ----------------- | ----------------- | --------------------------- |
| `DeepRagResponse` | `DeepRagResponse` | The Deep RAG task response. |

### search

```
search(
    name,
    query,
    number_of_results=10,
    folder_key=None,
    folder_path=None,
)
```

Search for contextual information within a specific index.

This method performs a semantic search against the specified context index, helping to find relevant information that can be used in automation processes. The search is powered by AI and understands natural language queries.

Parameters:

| Name                | Type  | Description                                          | Default    |
| ------------------- | ----- | ---------------------------------------------------- | ---------- |
| `name`              | `str` | The name of the context index to search in.          | *required* |
| `query`             | `str` | The search query in natural language.                | *required* |
| `number_of_results` | `int` | Maximum number of results to return. Defaults to 10. | `10`       |

Returns:

| Type                                  | Description                                                                                                                    |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `list[ContextGroundingQueryResponse]` | List\[ContextGroundingQueryResponse\]: A list of search results, each containing relevant contextual information and metadata. |

### search_async

```
search_async(
    name,
    query,
    number_of_results=10,
    folder_key=None,
    folder_path=None,
)
```

Search asynchronously for contextual information within a specific index.

This method performs a semantic search against the specified context index, helping to find relevant information that can be used in automation processes. The search is powered by AI and understands natural language queries.

Parameters:

| Name                | Type  | Description                                          | Default    |
| ------------------- | ----- | ---------------------------------------------------- | ---------- |
| `name`              | `str` | The name of the context index to search in.          | *required* |
| `query`             | `str` | The search query in natural language.                | *required* |
| `number_of_results` | `int` | Maximum number of results to return. Defaults to 10. | `10`       |

Returns:

| Type                                  | Description                                                                                                                    |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `list[ContextGroundingQueryResponse]` | List\[ContextGroundingQueryResponse\]: A list of search results, each containing relevant contextual information and metadata. |

### start_deep_rag

```
start_deep_rag(
    name,
    index_name,
    prompt,
    glob_pattern="*",
    citation_mode=CitationMode.SKIP,
    folder_key=None,
    folder_path=None,
)
```

Starts a Deep RAG task on the targeted index.

Parameters:

| Name            | Type           | Description                                                                                       | Default    |
| --------------- | -------------- | ------------------------------------------------------------------------------------------------- | ---------- |
| `name`          | `str`          | The name of the Deep RAG task.                                                                    | *required* |
| `index_name`    | `str`          | The name of the context index to search in.                                                       | *required* |
| `prompt`        | `str`          | Describe the task: what to research across documents, what to synthesize and how to cite sources. | *required* |
| `glob_pattern`  | `str`          | The glob pattern to search in the index. Defaults to "\*".                                        | `'*'`      |
| `citation_mode` | `CitationMode` | The citation mode to use. Defaults to SKIP.                                                       | `SKIP`     |
| `folder_key`    | `str`          | The folder key where the index resides. Defaults to None.                                         | `None`     |
| `folder_path`   | `str`          | The folder path where the index resides. Defaults to None.                                        | `None`     |

Returns:

| Name                      | Type                      | Description                          |
| ------------------------- | ------------------------- | ------------------------------------ |
| `DeepRagCreationResponse` | `DeepRagCreationResponse` | The Deep RAG task creation response. |

### start_deep_rag_async

```
start_deep_rag_async(
    name,
    index_name,
    prompt,
    glob_pattern="*",
    citation_mode=CitationMode.SKIP,
    folder_key=None,
    folder_path=None,
)
```

Asynchronously starts a Deep RAG task on the targeted index.

Parameters:

| Name            | Type           | Description                                                                                       | Default    |
| --------------- | -------------- | ------------------------------------------------------------------------------------------------- | ---------- |
| `name`          | `str`          | The name of the Deep RAG task.                                                                    | *required* |
| `index_name`    | `str`          | The name of the context index to search in.                                                       | *required* |
| `name`          | `str`          | The name of the Deep RAG task.                                                                    | *required* |
| `prompt`        | `str`          | Describe the task: what to research across documents, what to synthesize and how to cite sources. | *required* |
| `glob_pattern`  | `str`          | The glob pattern to search in the index. Defaults to "\*".                                        | `'*'`      |
| `citation_mode` | `CitationMode` | The citation mode to use. Defaults to SKIP.                                                       | `SKIP`     |
| `folder_key`    | `str`          | The folder key where the index resides. Defaults to None.                                         | `None`     |
| `folder_path`   | `str`          | The folder path where the index resides. Defaults to None.                                        | `None`     |

Returns:

| Name                      | Type                      | Description                          |
| ------------------------- | ------------------------- | ------------------------------------ |
| `DeepRagCreationResponse` | `DeepRagCreationResponse` | The Deep RAG task creation response. |
