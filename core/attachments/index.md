## AttachmentsService

Service for managing UiPath attachments.

Attachments allow you to upload and download files to be used within UiPath processes, actions, and other UiPath services.

Reference: <https://docs.uipath.com/orchestrator/reference/api-attachments>

### custom_headers

```
custom_headers
```

Return custom headers for API requests.

### delete

```
delete(*, key, folder_key=None, folder_path=None)
```

Delete an attachment.

This method deletes an attachment from UiPath. If the attachment is not found in UiPath (404 error), it will check for a local file in the temporary directory that matches the UUID.

Note

The local file fallback functionality is intended for local development and debugging purposes only.

Parameters:

| Name          | Type   | Description                          | Default                                                                 |
| ------------- | ------ | ------------------------------------ | ----------------------------------------------------------------------- |
| `key`         | `UUID` | The key of the attachment to delete. | *required*                                                              |
| `folder_key`  | \`str  | None\`                               | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str  | None\`                               | The path of the folder. Override the default one set in the SDK config. |

Raises:

| Type        | Description                                       |
| ----------- | ------------------------------------------------- |
| `Exception` | If the deletion fails and no local file is found. |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

client.attachments.delete(
    key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
)
print("Attachment deleted successfully")
```

### delete_async

```
delete_async(*, key, folder_key=None, folder_path=None)
```

Delete an attachment asynchronously.

This method asynchronously deletes an attachment from UiPath. If the attachment is not found in UiPath (404 error), it will check for a local file in the temporary directory that matches the UUID.

Note

The local file fallback functionality is intended for local development and debugging purposes only.

Parameters:

| Name          | Type   | Description                          | Default                                                                 |
| ------------- | ------ | ------------------------------------ | ----------------------------------------------------------------------- |
| `key`         | `UUID` | The key of the attachment to delete. | *required*                                                              |
| `folder_key`  | \`str  | None\`                               | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str  | None\`                               | The path of the folder. Override the default one set in the SDK config. |

Raises:

| Type        | Description                                       |
| ----------- | ------------------------------------------------- |
| `Exception` | If the deletion fails and no local file is found. |

Examples:

```
import asyncio
from uipath.platform import UiPath

client = UiPath()

async def main():
    await client.attachments.delete_async(
        key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    )
    print("Attachment deleted successfully")
```

### download

```
download(
    *,
    key,
    destination_path,
    folder_key=None,
    folder_path=None,
)
```

Download an attachment.

This method downloads an attachment from UiPath to a local file. If the attachment is not found in UiPath (404 error), it will check for a local file in the temporary directory that matches the UUID.

Note

The local file fallback functionality is intended for local development and debugging purposes only.

Parameters:

| Name               | Type   | Description                                        | Default                                                                 |
| ------------------ | ------ | -------------------------------------------------- | ----------------------------------------------------------------------- |
| `key`              | `UUID` | The key of the attachment to download.             | *required*                                                              |
| `destination_path` | `str`  | The local path where the attachment will be saved. | *required*                                                              |
| `folder_key`       | \`str  | None\`                                             | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path`      | \`str  | None\`                                             | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Name  | Type  | Description                            |
| ----- | ----- | -------------------------------------- |
| `str` | `str` | The name of the downloaded attachment. |

Raises:

| Type        | Description                                       |
| ----------- | ------------------------------------------------- |
| `Exception` | If the download fails and no local file is found. |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

attachment_name = client.attachments.download(
    key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
    destination_path="path/to/save/document.pdf"
)
print(f"Downloaded attachment: {attachment_name}")
```

### download_async

```
download_async(
    *,
    key,
    destination_path,
    folder_key=None,
    folder_path=None,
)
```

Download an attachment asynchronously.

This method asynchronously downloads an attachment from UiPath to a local file. If the attachment is not found in UiPath (404 error), it will check for a local file in the temporary directory that matches the UUID.

Note

The local file fallback functionality is intended for local development and debugging purposes only.

Parameters:

| Name               | Type   | Description                                        | Default                                                                 |
| ------------------ | ------ | -------------------------------------------------- | ----------------------------------------------------------------------- |
| `key`              | `UUID` | The key of the attachment to download.             | *required*                                                              |
| `destination_path` | `str`  | The local path where the attachment will be saved. | *required*                                                              |
| `folder_key`       | \`str  | None\`                                             | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path`      | \`str  | None\`                                             | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Name  | Type  | Description                            |
| ----- | ----- | -------------------------------------- |
| `str` | `str` | The name of the downloaded attachment. |

Raises:

| Type        | Description                                       |
| ----------- | ------------------------------------------------- |
| `Exception` | If the download fails and no local file is found. |

Examples:

```
import asyncio
from uipath.platform import UiPath

client = UiPath()

async def main():
    attachment_name = await client.attachments.download_async(
        key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
        destination_path="path/to/save/document.pdf"
    )
    print(f"Downloaded attachment: {attachment_name}")
```

### get_blob_file_access_uri

```
get_blob_file_access_uri(
    *, key, folder_key=None, folder_path=None
)
```

Get the BlobFileAccess information for an attachment.

This method retrieves the blob storage URI and filename for downloading an attachment without actually downloading the file.

Parameters:

| Name          | Type   | Description                | Default                                                                 |
| ------------- | ------ | -------------------------- | ----------------------------------------------------------------------- |
| `key`         | `UUID` | The key of the attachment. | *required*                                                              |
| `folder_key`  | \`str  | None\`                     | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str  | None\`                     | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Name                 | Type                 | Description                                                 |
| -------------------- | -------------------- | ----------------------------------------------------------- |
| `BlobFileAccessInfo` | `BlobFileAccessInfo` | Object containing the blob storage URI and attachment name. |

Raises:

| Type        | Description                                          |
| ----------- | ---------------------------------------------------- |
| `Exception` | If the attachment is not found or the request fails. |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

info = client.attachments.get_blob_file_access_uri(
    key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
)
print(f"Attachment ID: {info.id}")
print(f"Blob URI: {info.uri}")
print(f"File name: {info.name}")
```

### get_blob_file_access_uri_async

```
get_blob_file_access_uri_async(
    *, key, folder_key=None, folder_path=None
)
```

Get the BlobFileAccess information for an attachment asynchronously.

This method asynchronously retrieves the blob storage URI and filename for downloading an attachment without actually downloading the file.

Parameters:

| Name          | Type   | Description                | Default                                                                 |
| ------------- | ------ | -------------------------- | ----------------------------------------------------------------------- |
| `key`         | `UUID` | The key of the attachment. | *required*                                                              |
| `folder_key`  | \`str  | None\`                     | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str  | None\`                     | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Name                 | Type                 | Description                                                 |
| -------------------- | -------------------- | ----------------------------------------------------------- |
| `BlobFileAccessInfo` | `BlobFileAccessInfo` | Object containing the blob storage URI and attachment name. |

Raises:

| Type        | Description                                          |
| ----------- | ---------------------------------------------------- |
| `Exception` | If the attachment is not found or the request fails. |

Examples:

```
import asyncio
from uipath.platform import UiPath

client = UiPath()

async def main():
    info = await client.attachments.get_blob_file_access_uri_async(
        key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    )
    print(f"Attachment ID: {info.id}")
    print(f"Blob URI: {info.uri}")
    print(f"File name: {info.name}")
```

### open

```
open(
    *,
    attachment,
    mode=AttachmentMode.READ,
    content=None,
    folder_key=None,
    folder_path=None,
)
```

Open an attachment.

Parameters:

| Name          | Type             | Description             | Default                                                                 |
| ------------- | ---------------- | ----------------------- | ----------------------------------------------------------------------- |
| `attachment`  | `Attachment`     | The attachment to open. | *required*                                                              |
| `mode`        | `AttachmentMode` | The mode to use.        | `READ`                                                                  |
| `content`     | \`RequestContent | None\`                  | An optional request content to upload.                                  |
| `folder_key`  | \`str            | None\`                  | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str            | None\`                  | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Name  | Type                                    | Description                            |
| ----- | --------------------------------------- | -------------------------------------- |
| `str` | `Iterator[tuple[Attachment, Response]]` | The name of the downloaded attachment. |

Raises:

| Type        | Description                                       |
| ----------- | ------------------------------------------------- |
| `Exception` | If the download fails and no local file is found. |

### open_async

```
open_async(
    *,
    attachment,
    mode=AttachmentMode.READ,
    content=None,
    folder_key=None,
    folder_path=None,
)
```

Open an attachment asynchronously.

Parameters:

| Name          | Type             | Description                            | Default                                                                 |
| ------------- | ---------------- | -------------------------------------- | ----------------------------------------------------------------------- |
| `attachment`  | `Attachment`     | The attachment to open.                | *required*                                                              |
| `mode`        | `AttachmentMode` | The mode to use.                       | `READ`                                                                  |
| `content`     | `RequestContent` | An optional request content to upload. | `None`                                                                  |
| `folder_key`  | \`str            | None\`                                 | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str            | None\`                                 | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Name  | Type                                         | Description                            |
| ----- | -------------------------------------------- | -------------------------------------- |
| `str` | `AsyncIterator[tuple[Attachment, Response]]` | The name of the downloaded attachment. |

Raises:

| Type        | Description                                       |
| ----------- | ------------------------------------------------- |
| `Exception` | If the download fails and no local file is found. |

### upload

```
upload(
    *,
    name,
    content=None,
    source_path=None,
    folder_key=None,
    folder_path=None,
)
```

Upload a file or content to UiPath as an attachment.

This method uploads content to UiPath and makes it available as an attachment. You can either provide a file path or content in memory.

Parameters:

| Name          | Type  | Description                      | Default                                                                 |
| ------------- | ----- | -------------------------------- | ----------------------------------------------------------------------- |
| `name`        | `str` | The name of the attachment file. | *required*                                                              |
| `content`     | \`str | bytes                            | None\`                                                                  |
| `source_path` | \`str | None\`                           | The local path of the file to upload.                                   |
| `folder_key`  | \`str | None\`                           | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                           | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Type   | Description                                    |
| ------ | ---------------------------------------------- |
| `UUID` | uuid.UUID: The UUID of the created attachment. |

Raises:

| Type         | Description                                                              |
| ------------ | ------------------------------------------------------------------------ |
| `ValueError` | If neither content nor source_path is provided, or if both are provided. |
| `Exception`  | If the upload fails.                                                     |

Examples:

```
from uipath.platform import UiPath

client = UiPath()

# Upload a file from disk
attachment_key = client.attachments.upload(
    name="my-document.pdf",
    source_path="path/to/local/document.pdf",
)
print(f"Uploaded attachment with key: {attachment_key}")

# Upload content from memory
attachment_key = client.attachments.upload(
    name="notes.txt",
    content="This is a text file content",
)
print(f"Uploaded attachment with key: {attachment_key}")
```

### upload_async

```
upload_async(
    *,
    name,
    content=None,
    source_path=None,
    folder_key=None,
    folder_path=None,
)
```

Upload a file or content to UiPath as an attachment asynchronously.

This method asynchronously uploads content to UiPath and makes it available as an attachment. You can either provide a file path or content in memory.

Parameters:

| Name          | Type  | Description                      | Default                                                                 |
| ------------- | ----- | -------------------------------- | ----------------------------------------------------------------------- |
| `name`        | `str` | The name of the attachment file. | *required*                                                              |
| `content`     | \`str | bytes                            | None\`                                                                  |
| `source_path` | \`str | None\`                           | The local path of the file to upload.                                   |
| `folder_key`  | \`str | None\`                           | The key of the folder. Override the default one set in the SDK config.  |
| `folder_path` | \`str | None\`                           | The path of the folder. Override the default one set in the SDK config. |

Returns:

| Type   | Description                                    |
| ------ | ---------------------------------------------- |
| `UUID` | uuid.UUID: The UUID of the created attachment. |

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
    # Upload a file from disk
    attachment_key = await client.attachments.upload_async(
        name="my-document.pdf",
        source_path="path/to/local/document.pdf",
    )
    print(f"Uploaded attachment with key: {attachment_key}")

    # Upload content from memory
    attachment_key = await client.attachments.upload_async(
        name="notes.txt",
        content="This is a text file content",
    )
    print(f"Uploaded attachment with key: {attachment_key}")
```
