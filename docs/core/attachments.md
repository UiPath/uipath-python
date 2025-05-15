# Attachments Service

The `AttachmentsService` provides methods to upload, download, and delete attachments in UiPath Orchestrator. Attachments are files that can be associated with jobs, processes, or other entities, and are managed via the Orchestrator API.

> **Reference:** [UiPath Orchestrator Attachments API](https://docs.uipath.com/orchestrator/reference/api-attachments)

## Features
- Upload files or in-memory content as attachments
- Download attachments to local files
- Delete attachments
- Both synchronous and asynchronous methods

## Usage

### Instantiating the Service

The `AttachmentsService` is available as a property on the main `UiPath` client:

```python
from uipath import UiPath

client = UiPath()
attachments = client.attachments
```

### Uploading an Attachment

You can upload a file from disk or from memory:

```python
# Upload from file
attachment_key = client.attachments.upload(
    name="document.pdf",
    source_path="/path/to/document.pdf",
)

# Upload from memory
attachment_key = client.attachments.upload(
    name="notes.txt",
    content="Some text content",
)
```

#### Async Example
```python
attachment_key = await client.attachments.upload_async(
    name="notes.txt",
    content="Some text content",
)
```

### Downloading an Attachment

```python
attachment_name = client.attachments.download(
    key=attachment_key,
    destination_path="/path/to/save/document.pdf",
)
```

#### Async Example
```python
attachment_name = await client.attachments.download_async(
    key=attachment_key,
    destination_path="/path/to/save/document.pdf",
)
```

### Deleting an Attachment

```python
client.attachments.delete(key=attachment_key)
```

#### Async Example
```python
await client.attachments.delete_async(key=attachment_key)
```

## Error Handling

All methods raise exceptions on failure. See the SDK error handling documentation for details.

## See Also
- [UiPath Orchestrator Attachments API](https://docs.uipath.com/orchestrator/reference/api-attachments)
- [Jobs Service](./jobs.md) for listing attachments associated with jobs. 