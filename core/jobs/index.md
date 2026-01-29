## JobsService

Service for managing API payloads and job inbox interactions.

A job represents a single execution of an automation - it is created when you start a process and contains information about that specific run, including its status, start time, and any input/output data.

### create_attachment

```
create_attachment(
    *,
    name,
    content=None,
    source_path=None,
    job_key=None,
    category=None,
    folder_key=None,
    folder_path=None,
)
```

Create and upload an attachment, optionally linking it to a job.

This method handles creating an attachment from a file or memory data. If a job key is provided or available in the execution context, the attachment will be created in UiPath and linked to the job. If no job is available, the file will be saved to a temporary storage folder.

Note

The local storage functionality (when no job is available) is intended for local development and debugging purposes only.

Parameters:

| Name          | Type  | Description                      | Default                                                                 |
| ------------- | ----- | -------------------------------- | ----------------------------------------------------------------------- |
| `name`        | `str` | The name of the attachment file. | *required*                                                              |
| `content`     | \`str | bytes                            | None\`                                                                  |
| `source_path` | \`str | Path                             | None\`                                                                  |
| `job_key`     | \`str | UUID                             | None\`                                                                  |
| `category`    | \`str | None\`                           | Optional category for the attachment in the context of the job.         |
| `folder_key`  | \`str | None\`                           | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                           | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Type   | Description                                                                                                                     |
| ------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `UUID` | uuid.UUID: The unique identifier for the created attachment, regardless of whether it was uploaded to UiPath or stored locally. |

Raises:

| Type         | Description                                                              |
| ------------ | ------------------------------------------------------------------------ |
| `ValueError` | If neither content nor source_path is provided, or if both are provided. |
| `Exception`  | If the upload fails.                                                     |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

# Create attachment from file and link to job
attachment_id = client.jobs.create_attachment(
    name="document.pdf",
    source_path="path/to/local/document.pdf",
    job_key="38073051"
)
print(f"Created and linked attachment: {attachment_id}")

# Create attachment from memory content (no job available - saves to temp storage)
attachment_id = client.jobs.create_attachment(
    name="report.txt",
    content="This is a text report"
)
print(f"Created attachment: {attachment_id}")
```

### create_attachment_async

```
create_attachment_async(
    *,
    name,
    content=None,
    source_path=None,
    job_key=None,
    category=None,
    folder_key=None,
    folder_path=None,
)
```

Create and upload an attachment asynchronously, optionally linking it to a job.

This method asynchronously handles creating an attachment from a file or memory data. If a job key is provided or available in the execution context, the attachment will be created in UiPath and linked to the job. If no job is available, the file will be saved to a temporary storage folder.

Note

The local storage functionality (when no job is available) is intended for local development and debugging purposes only.

Parameters:

| Name          | Type  | Description                      | Default                                                                 |
| ------------- | ----- | -------------------------------- | ----------------------------------------------------------------------- |
| `name`        | `str` | The name of the attachment file. | *required*                                                              |
| `content`     | \`str | bytes                            | None\`                                                                  |
| `source_path` | \`str | Path                             | None\`                                                                  |
| `job_key`     | \`str | UUID                             | None\`                                                                  |
| `category`    | \`str | None\`                           | Optional category for the attachment in the context of the job.         |
| `folder_key`  | \`str | None\`                           | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                           | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Type   | Description                                                                                                                     |
| ------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `UUID` | uuid.UUID: The unique identifier for the created attachment, regardless of whether it was uploaded to UiPath or stored locally. |

Raises:

| Type         | Description                                                              |
| ------------ | ------------------------------------------------------------------------ |
| `ValueError` | If neither content nor source_path is provided, or if both are provided. |
| `Exception`  | If the upload fails.                                                     |

Examples:

```
import asyncio
from uipath.platform import UiPath

client = UiPath()

async def main():
    # Create attachment from file and link to job
    attachment_id = await client.jobs.create_attachment_async(
        name="document.pdf",
        source_path="path/to/local/document.pdf",
        job_key="38073051"
    )
    print(f"Created and linked attachment: {attachment_id}")

    # Create attachment from memory content (no job available - saves to temp storage)
    attachment_id = await client.jobs.create_attachment_async(
        name="report.txt",
        content="This is a text report"
    )
    print(f"Created attachment: {attachment_id}")
```

### exists

```
exists(job_key, *, folder_key=None, folder_path=None)
```

Check if job exists.

Parameters:

| Name          | Type  | Description  | Default     |
| ------------- | ----- | ------------ | ----------- |
| `job_key`     | `str` | Job UUID key | *required*  |
| `folder_key`  | \`str | None\`       | Folder key  |
| `folder_path` | \`str | None\`       | Folder path |

Returns:

| Name   | Type   | Description                         |
| ------ | ------ | ----------------------------------- |
| `bool` | `bool` | True if job exists, False otherwise |

Examples:

```
>>> if sdk.jobs.exists(job_key="ee9327fd-237d-419e-86ef-9946b34461e3"):
...     print("Job found")
```

### exists_async

```
exists_async(job_key, *, folder_key=None, folder_path=None)
```

Async version of exists().

### extract_output

```
extract_output(job)
```

Get the actual output data, downloading from attachment if necessary.

Parameters:

| Name  | Type  | Description                                 | Default    |
| ----- | ----- | ------------------------------------------- | ---------- |
| `job` | `Job` | The job instance to fetch output data from. | *required* |

Returns:

| Type  | Description |
| ----- | ----------- |
| \`str | None\`      |

### extract_output_async

```
extract_output_async(job)
```

Asynchronously fetch the actual output data, downloading from attachment if necessary.

Parameters:

| Name  | Type  | Description                                 | Default    |
| ----- | ----- | ------------------------------------------- | ---------- |
| `job` | `Job` | The job instance to fetch output data from. | *required* |

Returns:

| Type  | Description |
| ----- | ----------- |
| \`str | None\`      |

### link_attachment

```
link_attachment(
    *,
    attachment_key,
    job_key,
    category=None,
    folder_key=None,
    folder_path=None,
)
```

Link an attachment to a job.

This method links an existing attachment to a specific job.

Parameters:

| Name             | Type   | Description                                   | Default                                                                 |
| ---------------- | ------ | --------------------------------------------- | ----------------------------------------------------------------------- |
| `attachment_key` | `UUID` | The key of the attachment to link.            | *required*                                                              |
| `job_key`        | `UUID` | The key of the job to link the attachment to. | *required*                                                              |
| `category`       | \`str  | None\`                                        | Optional category for the attachment in the context of this job.        |
| `folder_key`     | \`str  | None\`                                        | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path`    | \`str  | None\`                                        | The path of the folder. Override the default one set in the SDK config. |

Raises:

| Type        | Description                  |
| ----------- | ---------------------------- |
| `Exception` | If the link operation fails. |

### link_attachment_async

```
link_attachment_async(
    *,
    attachment_key,
    job_key,
    category=None,
    folder_key=None,
    folder_path=None,
)
```

Link an attachment to a job asynchronously.

This method asynchronously links an existing attachment to a specific job.

Parameters:

| Name             | Type   | Description                                   | Default                                                                 |
| ---------------- | ------ | --------------------------------------------- | ----------------------------------------------------------------------- |
| `attachment_key` | `UUID` | The key of the attachment to link.            | *required*                                                              |
| `job_key`        | `UUID` | The key of the job to link the attachment to. | *required*                                                              |
| `category`       | \`str  | None\`                                        | Optional category for the attachment in the context of this job.        |
| `folder_key`     | \`str  | None\`                                        | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path`    | \`str  | None\`                                        | The path of the folder. Override the default one set in the SDK config. |

Raises:

| Type        | Description                  |
| ----------- | ---------------------------- |
| `Exception` | If the link operation fails. |

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

List jobs using OData API with offset-based pagination.

Returns a single page of results with pagination metadata.

Parameters:

| Name          | Type  | Description                                    | Default                                                  |
| ------------- | ----- | ---------------------------------------------- | -------------------------------------------------------- |
| `folder_path` | \`str | None\`                                         | Folder path to filter jobs                               |
| `folder_key`  | \`str | None\`                                         | Folder key (mutually exclusive with folder_path)         |
| `filter`      | \`str | None\`                                         | OData $filter expression (e.g., "State eq 'Successful'") |
| `orderby`     | \`str | None\`                                         | OData $orderby expression (e.g., "CreationTime desc")    |
| `skip`        | `int` | Number of items to skip (default 0, max 10000) | `0`                                                      |
| `top`         | `int` | Maximum items per page (default 100, max 1000) | `100`                                                    |

Returns:

| Type               | Description                                               |
| ------------------ | --------------------------------------------------------- |
| `PagedResult[Job]` | PagedResult\[Job\]: Page of jobs with pagination metadata |

Raises:

| Type         | Description                           |
| ------------ | ------------------------------------- |
| `ValueError` | If skip or top parameters are invalid |

Examples:

```
>>> result = sdk.jobs.list(top=100)
>>> for job in result.items:
...     print(job.key, job.state)
>>> print(f"Has more: {result.has_more}")
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

Async version of list() with offset-based pagination.

### list_attachments

```
list_attachments(
    *, job_key, folder_key=None, folder_path=None
)
```

List attachments associated with a specific job.

This method retrieves all attachments linked to a job by its key.

Parameters:

| Name          | Type   | Description                                     | Default                                                                 |
| ------------- | ------ | ----------------------------------------------- | ----------------------------------------------------------------------- |
| `job_key`     | `UUID` | The key of the job to retrieve attachments for. | *required*                                                              |
| `folder_key`  | \`str  | None\`                                          | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str  | None\`                                          | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Type        | Description                                                    |
| ----------- | -------------------------------------------------------------- |
| `list[str]` | List\[str\]: A list of attachment IDs associated with the job. |

Raises:

| Type        | Description             |
| ----------- | ----------------------- |
| `Exception` | If the retrieval fails. |

### list_attachments_async

```
list_attachments_async(
    *, job_key, folder_key=None, folder_path=None
)
```

List attachments associated with a specific job asynchronously.

This method asynchronously retrieves all attachments linked to a job by its key.

Parameters:

| Name          | Type   | Description                                     | Default                                                                 |
| ------------- | ------ | ----------------------------------------------- | ----------------------------------------------------------------------- |
| `job_key`     | `UUID` | The key of the job to retrieve attachments for. | *required*                                                              |
| `folder_key`  | \`str  | None\`                                          | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str  | None\`                                          | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Type        | Description                                                    |
| ----------- | -------------------------------------------------------------- |
| `list[str]` | List\[str\]: A list of attachment IDs associated with the job. |

Raises:

| Type        | Description             |
| ----------- | ----------------------- |
| `Exception` | If the retrieval fails. |

Examples:

```
import asyncio
from uipath.platform import UiPath

client = UiPath()

async def main():
    attachments = await client.jobs.list_attachments_async(
        job_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    )
    for attachment_id in attachments:
        print(f"Attachment ID: {attachment_id}")
```

### restart

```
restart(*, job_key, folder_path=None, folder_key=None)
```

Restart a completed or failed job.

Parameters:

| Name          | Type  | Description             | Default     |
| ------------- | ----- | ----------------------- | ----------- |
| `job_key`     | `str` | Job UUID key to restart | *required*  |
| `folder_path` | \`str | None\`                  | Folder path |
| `folder_key`  | \`str | None\`                  | Folder key  |

Returns:

| Name  | Type  | Description       |
| ----- | ----- | ----------------- |
| `Job` | `Job` | The restarted job |

Examples:

```
>>> restarted_job = sdk.jobs.restart(job_key="ee9327fd-237d-419e-86ef-9946b34461e3")
>>> print(restarted_job.state)
```

### restart_async

```
restart_async(
    *, job_key, folder_path=None, folder_key=None
)
```

Async version of restart().

### resume

```
resume(
    *,
    inbox_id=None,
    job_id=None,
    folder_key=None,
    folder_path=None,
    payload,
)
```

Sends a payload to resume a paused job waiting for input, identified by its inbox ID.

Parameters:

| Name          | Type  | Description             | Default                                                                                           |
| ------------- | ----- | ----------------------- | ------------------------------------------------------------------------------------------------- |
| `inbox_id`    | \`str | None\`                  | The inbox ID of the job.                                                                          |
| `job_id`      | \`str | None\`                  | The job ID of the job.                                                                            |
| `folder_key`  | \`str | None\`                  | The key of the folder to execute the process in. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                  | The path of the folder to execute the process in. Override the default one set in the SDK config. |
| `payload`     | `Any` | The payload to deliver. | *required*                                                                                        |

### resume_async

```
resume_async(
    *,
    inbox_id=None,
    job_id=None,
    folder_key=None,
    folder_path=None,
    payload,
)
```

Asynchronously sends a payload to resume a paused job waiting for input, identified by its inbox ID.

Parameters:

| Name          | Type  | Description             | Default                                                                                                |
| ------------- | ----- | ----------------------- | ------------------------------------------------------------------------------------------------------ |
| `inbox_id`    | \`str | None\`                  | The inbox ID of the job. If not provided, the execution context will be used to retrieve the inbox ID. |
| `job_id`      | \`str | None\`                  | The job ID of the job.                                                                                 |
| `folder_key`  | \`str | None\`                  | The key of the folder to execute the process in. Override the default one set in the SDK config.       |
| `folder_path` | \`str | None\`                  | The path of the folder to execute the process in. Override the default one set in the SDK config.      |
| `payload`     | `Any` | The payload to deliver. | *required*                                                                                             |

Examples:

```
import asyncio

from uipath.platform import UiPath

sdk = UiPath()


async def main():  # noqa: D103
    payload = await sdk.jobs.resume_async(job_id="38073051", payload="The response")

asyncio.run(main())
```

### retrieve

```
retrieve(
    job_key,
    *,
    folder_key=None,
    folder_path=None,
    process_name=None,
)
```

Retrieve a job identified by its key.

Parameters:

| Name           | Type  | Description                | Default                                               |
| -------------- | ----- | -------------------------- | ----------------------------------------------------- |
| `job_key`      | `str` | The job unique identifier. | *required*                                            |
| `folder_key`   | \`str | None\`                     | The key of the folder in which the job was executed.  |
| `folder_path`  | \`str | None\`                     | The path of the folder in which the job was executed. |
| `process_name` | \`str | None\`                     | process name hint for resource override               |

Returns:

| Name  | Type  | Description        |
| ----- | ----- | ------------------ |
| `Job` | `Job` | The retrieved job. |

Raises:

| Type          | Description                                     |
| ------------- | ----------------------------------------------- |
| `LookupError` | If the job with the specified key is not found. |

Examples:

```
from uipath.platform import UiPath

sdk = UiPath()
job = sdk.jobs.retrieve(job_key="ee9327fd-237d-419e-86ef-9946b34461e3", folder_path="Shared")
```

### retrieve_api_payload

```
retrieve_api_payload(inbox_id)
```

Fetch payload data for API triggers.

Parameters:

| Name       | Type  | Description                                   | Default    |
| ---------- | ----- | --------------------------------------------- | ---------- |
| `inbox_id` | `str` | The Id of the inbox to fetch the payload for. | *required* |

Returns:

| Type  | Description                                    |
| ----- | ---------------------------------------------- |
| `Any` | The value field from the API response payload. |

### retrieve_api_payload_async

```
retrieve_api_payload_async(inbox_id)
```

Asynchronously fetch payload data for API triggers.

Parameters:

| Name       | Type  | Description                                   | Default    |
| ---------- | ----- | --------------------------------------------- | ---------- |
| `inbox_id` | `str` | The Id of the inbox to fetch the payload for. | *required* |

Returns:

| Type  | Description                                    |
| ----- | ---------------------------------------------- |
| `Any` | The value field from the API response payload. |

### retrieve_async

```
retrieve_async(
    job_key,
    *,
    folder_key=None,
    folder_path=None,
    process_name=None,
)
```

Asynchronously retrieve a job identified by its key.

Parameters:

| Name           | Type  | Description                | Default                                               |
| -------------- | ----- | -------------------------- | ----------------------------------------------------- |
| `job_key`      | `str` | The job unique identifier. | *required*                                            |
| `folder_key`   | \`str | None\`                     | The key of the folder in which the job was executed.  |
| `folder_path`  | \`str | None\`                     | The path of the folder in which the job was executed. |
| `process_name` | \`str | None\`                     | process name hint for resource override               |

Returns:

| Name  | Type  | Description        |
| ----- | ----- | ------------------ |
| `Job` | `Job` | The retrieved job. |

Raises:

| Type          | Description                                     |
| ------------- | ----------------------------------------------- |
| `LookupError` | If the job with the specified key is not found. |

Examples:

```
import asyncio

from uipath.platform import UiPath

sdk = UiPath()


async def main():  # noqa: D103
    job = await sdk.jobs.retrieve_async(job_key="ee9327fd-237d-419e-86ef-9946b34461e3", folder_path="Shared")

asyncio.run(main())
```

### stop

```
stop(
    *,
    job_keys,
    strategy="SoftStop",
    folder_path=None,
    folder_key=None,
)
```

Stop one or more jobs with specified strategy.

This method uses bulk resolution to efficiently stop multiple jobs, preventing N+1 query issues. Requests are automatically chunked for large job lists to avoid URL length constraints.

Parameters:

| Name          | Type        | Description                                             | Default      |
| ------------- | ----------- | ------------------------------------------------------- | ------------ |
| `job_keys`    | `list[str]` | List of job UUID keys to stop                           | *required*   |
| `strategy`    | `str`       | Stop strategy - "SoftStop" (graceful) or "Kill" (force) | `'SoftStop'` |
| `folder_path` | \`str       | None\`                                                  | Folder path  |
| `folder_key`  | \`str       | None\`                                                  | Folder key   |

Raises:

| Type          | Description                               |
| ------------- | ----------------------------------------- |
| `ValueError`  | If any job key is not a valid UUID format |
| `LookupError` | If any job keys are not found             |

Examples:

```
>>> sdk.jobs.stop(job_keys=["ee9327fd-237d-419e-86ef-9946b34461e3"])
>>> sdk.jobs.stop(job_keys=["key1", "key2"], strategy="Kill")
```

Note

Large batches are automatically chunked (50 keys per request) to avoid URL length limits. The method supports stopping hundreds of jobs efficiently.

### stop_async

```
stop_async(
    *,
    job_keys,
    strategy="SoftStop",
    folder_path=None,
    folder_key=None,
)
```

Async version of stop().
