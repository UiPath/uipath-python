Ontology service: an ontology by id, its artifacts, its graph and SQL over it.

Backend target: `ontology_/api/v1`. The ontology id is its key in the Resource Catalog and in Solutions; the routes also accept the ontology's name, which is folder-scoped, so an `ontology` binding can re-point a call to a name in a folder.

Honors `UIPATH_SERVICE_URL_ONTOLOGY` for local development, as every service does: `BaseService.request` redirects the call and injects the routing headers.

## OntologyService

Service for reading a deployed ontology and querying its objects.

Every method takes the ontology's id. An `ontology` binding can replace that id with an ontology name and a folder; names are folder-scoped on the service, so the folder travels as the folder header.

Preview Feature

This service is currently experimental. Behavior and parameters are subject to change in future versions.

Examples:

```
from uipath.platform import UiPath

sdk = UiPath()
details = await sdk.ontology.get_async(ontology_id)
if details.is_deployed:
    files = await sdk.ontology.download_artifacts_async(ontology_id, "schema")
    answer = await sdk.ontology.execute_sql_async(
        ontology_id, "SELECT name FROM Supplier WHERE country = :c", {"c": "RO"}
    )
```

### download_artifacts

```
download_artifacts(
    ontology_id,
    artifact_type=None,
    *,
    max_bytes=DEFAULT_MAX_ARTIFACT_BYTES,
    folder_key=None,
    folder_path=None,
)
```

Download every artifact of a type, verified against the manifest.

Files larger than `max_bytes` are not downloaded. They come back in `skipped` with their size, so a caller can tell a file that was too large from one the ontology does not have.

Parameters:

| Name            | Type  | Description                                         | Default                                                           |
| --------------- | ----- | --------------------------------------------------- | ----------------------------------------------------------------- |
| `ontology_id`   | `str` | The ontology's id, or its name with a folder.       | *required*                                                        |
| `artifact_type` | \`str | None\`                                              | Keep one type only; every type when omitted.                      |
| `max_bytes`     | `int` | The largest file to download, by its manifest size. | `DEFAULT_MAX_ARTIFACT_BYTES`                                      |
| `folder_key`    | \`str | None\`                                              | The key of the ontology's folder; needed when addressing by name. |
| `folder_path`   | \`str | None\`                                              | The path of the ontology's folder; exclusive with folder_key.     |

Returns:

| Name               | Type               | Description                                           |
| ------------------ | ------------------ | ----------------------------------------------------- |
| `ArtifactDownload` | `ArtifactDownload` | the verified files in manifest order, and the entries |
|                    | `ArtifactDownload` | skipped for size.                                     |

### download_artifacts_async

```
download_artifacts_async(
    ontology_id,
    artifact_type=None,
    *,
    max_bytes=DEFAULT_MAX_ARTIFACT_BYTES,
    folder_key=None,
    folder_path=None,
)
```

Download every artifact of a type. See :meth:`download_artifacts`.

The files are fetched concurrently, at most `MAX_CONCURRENT_DOWNLOADS` at a time, and keep manifest order. Any failed or mismatched download fails the call, as in the sync variant.

### execute_sql

```
execute_sql(
    ontology_id,
    statement,
    params=None,
    *,
    folder_key=None,
    folder_path=None,
)
```

Run one SELECT over the ontology's objects.

The statement is written over business objects and their properties, with `:name` parameters bound from `params`; the service translates it onto the mapped entities and runs it with the caller's permissions. Values go in `params`, never in the statement text.

Paging is part of the statement: without a LIMIT the service reads 50 rows, a LIMIT is at most 200, and OFFSET with ORDER BY reads a later page.

Parameters:

| Name          | Type             | Description                                   | Default                                                           |
| ------------- | ---------------- | --------------------------------------------- | ----------------------------------------------------------------- |
| `ontology_id` | `str`            | The ontology's id, or its name with a folder. | *required*                                                        |
| `statement`   | `str`            | The SELECT, with :name placeholders.          | *required*                                                        |
| `params`      | \`dict[str, Any] | None\`                                        | Values for the placeholders.                                      |
| `folder_key`  | \`str            | None\`                                        | The key of the ontology's folder; needed when addressing by name. |
| `folder_path` | \`str            | None\`                                        | The path of the ontology's folder; exclusive with folder_key.     |

Returns:

| Name        | Type        | Description                                  |
| ----------- | ----------- | -------------------------------------------- |
| `SqlResult` | `SqlResult` | columns, rows as objects, and the row count. |

Raises:

| Type         | Description                |
| ------------ | -------------------------- |
| `ValueError` | If the statement is blank. |

### execute_sql_async

```
execute_sql_async(
    ontology_id,
    statement,
    params=None,
    *,
    folder_key=None,
    folder_path=None,
)
```

Run one SELECT over the ontology's objects. See :meth:`execute_sql`.

### get

```
get(ontology_id, *, folder_key=None, folder_path=None)
```

Read an ontology's catalog details.

Parameters:

| Name          | Type  | Description                                                                                     | Default                                                           |
| ------------- | ----- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `ontology_id` | `str` | The ontology's id (its Resource Catalog key), or its name together with the folder it lives in. | *required*                                                        |
| `folder_key`  | \`str | None\`                                                                                          | The key of the ontology's folder; needed when addressing by name. |
| `folder_path` | \`str | None\`                                                                                          | The path of the ontology's folder; exclusive with folder_key.     |

Returns:

| Name              | Type              | Description                                       |
| ----------------- | ----------------- | ------------------------------------------------- |
| `OntologyDetails` | `OntologyDetails` | identifier, label, description, folder and state. |

### get_artifact

```
get_artifact(
    ontology_id,
    file_name,
    *,
    expected=None,
    folder_key=None,
    folder_path=None,
)
```

Download one artifact's bytes.

Parameters:

| Name          | Type               | Description                                         | Default                                                                                                                          |
| ------------- | ------------------ | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `ontology_id` | `str`              | The ontology's id, or its name with a folder.       | *required*                                                                                                                       |
| `file_name`   | `str`              | The artifact's file name, as the manifest lists it. | *required*                                                                                                                       |
| `expected`    | \`OntologyArtifact | None\`                                              | The manifest entry to verify the download against. When given, a size or SHA-256 mismatch raises before the content is returned. |
| `folder_key`  | \`str              | None\`                                              | The key of the ontology's folder; needed when addressing by name.                                                                |
| `folder_path` | \`str              | None\`                                              | The path of the ontology's folder; exclusive with folder_key.                                                                    |

Returns:

| Name                      | Type                      | Description                               |
| ------------------------- | ------------------------- | ----------------------------------------- |
| `OntologyArtifactContent` | `OntologyArtifactContent` | the bytes, their media type and the ETag. |

Raises:

| Type                             | Description                                         |
| -------------------------------- | --------------------------------------------------- |
| `OntologyArtifactIntegrityError` | If expected is given and the bytes do not match it. |

### get_artifact_async

```
get_artifact_async(
    ontology_id,
    file_name,
    *,
    expected=None,
    folder_key=None,
    folder_path=None,
)
```

Download one artifact's bytes. See :meth:`get_artifact`.

### get_artifact_by_type

```
get_artifact_by_type(
    ontology_id,
    artifact_type,
    *,
    folder_key=None,
    folder_path=None,
)
```

Download the one artifact of a single-file type, such as the schema.

One request, no manifest: the service answers the type's file as a download by name does, and the content is verified against the checksum in its ETag.

Parameters:

| Name            | Type  | Description                                                                                                                                                  | Default                                                           |
| --------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| `ontology_id`   | `str` | The ontology's id, or its name with a folder.                                                                                                                | *required*                                                        |
| `artifact_type` | `str` | A single-file type: schema, mapping, summary or context. A type that can hold several files is refused by the service; list those with :meth:list_artifacts. | *required*                                                        |
| `folder_key`    | \`str | None\`                                                                                                                                                       | The key of the ontology's folder; needed when addressing by name. |
| `folder_path`   | \`str | None\`                                                                                                                                                       | The path of the ontology's folder; exclusive with folder_key.     |

Returns:

| Name                      | Type                      | Description                                      |
| ------------------------- | ------------------------- | ------------------------------------------------ |
| `OntologyArtifactContent` | `OntologyArtifactContent` | the bytes, their media type, file name and ETag. |

Raises:

| Type                             | Description                                  |
| -------------------------------- | -------------------------------------------- |
| `OntologyArtifactIntegrityError` | If the bytes do not match the ETag checksum. |

### get_artifact_by_type_async

```
get_artifact_by_type_async(
    ontology_id,
    artifact_type,
    *,
    folder_key=None,
    folder_path=None,
)
```

Download the one artifact of a single-file type. See :meth:`get_artifact_by_type`.

### get_async

```
get_async(
    ontology_id, *, folder_key=None, folder_path=None
)
```

Read an ontology's catalog details. See :meth:`get`.

### get_graph

```
get_graph(
    ontology_id, *, folder_key=None, folder_path=None
)
```

Read the ontology's graph: objects, properties, relationships, operations.

Returned as the service sends it, since its shape is still evolving.

Parameters:

| Name          | Type  | Description                                   | Default                                                           |
| ------------- | ----- | --------------------------------------------- | ----------------------------------------------------------------- |
| `ontology_id` | `str` | The ontology's id, or its name with a folder. | *required*                                                        |
| `folder_key`  | \`str | None\`                                        | The key of the ontology's folder; needed when addressing by name. |
| `folder_path` | \`str | None\`                                        | The path of the ontology's folder; exclusive with folder_key.     |

Returns:

| Type             | Description                       |
| ---------------- | --------------------------------- |
| `dict[str, Any]` | Dict\[str, Any\]: the graph view. |

### get_graph_async

```
get_graph_async(
    ontology_id, *, folder_key=None, folder_path=None
)
```

Read the ontology's graph. See :meth:`get_graph`.

### list_artifacts

```
list_artifacts(
    ontology_id,
    artifact_type=None,
    *,
    folder_key=None,
    folder_path=None,
)
```

List an ontology's artifacts: the manifest, without content.

Parameters:

| Name            | Type  | Description                                   | Default                                                                                                                              |
| --------------- | ----- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `ontology_id`   | `str` | The ontology's id, or its name with a folder. | *required*                                                                                                                           |
| `artifact_type` | \`str | None\`                                        | Keep one type only: schema, mapping, business-rules, summary, context (or constraints). The service answers 400 for an unknown type. |
| `folder_key`    | \`str | None\`                                        | The key of the ontology's folder; needed when addressing by name.                                                                    |
| `folder_path`   | \`str | None\`                                        | The path of the ontology's folder; exclusive with folder_key.                                                                        |

Returns:

| Type                     | Description                                                          |
| ------------------------ | -------------------------------------------------------------------- |
| `list[OntologyArtifact]` | List\[OntologyArtifact\]: one entry per file, with size and SHA-256. |

### list_artifacts_async

```
list_artifacts_async(
    ontology_id,
    artifact_type=None,
    *,
    folder_key=None,
    folder_path=None,
)
```

List an ontology's artifacts. See :meth:`list_artifacts`.
