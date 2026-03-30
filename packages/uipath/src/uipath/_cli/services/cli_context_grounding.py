"""Context Grounding service commands for UiPath CLI.

Context Grounding provides capabilities for indexing, retrieving, and searching
through contextual information used to enhance AI-enabled automation.
"""
# ruff: noqa: D301 - Click uses \b in docstrings for formatting

import json as json_module
from typing import Any, Optional

import click

from .._utils._service_base import (
    ServiceCommandBase,
    common_service_options,
    handle_not_found_error,
    service_command,
)


@click.group(name="context-grounding")
def context_grounding() -> None:
    """Manage UiPath Context Grounding indexes.

    Context Grounding indexes store and search contextual information
    used to enhance AI-enabled automation processes.

    \b
    Two index types:
        Regular   - Persistent, backed by bucket or connection, created via 'create'
        Ephemeral - Temporary, no Orchestrator folder, created from local files via 'create-ephemeral'

    \b
    Examples:
        uipath context-grounding list --folder-path "Shared"
    """
    pass


@context_grounding.command(name="list")
@common_service_options
@service_command
def list_indexes(
    ctx: click.Context,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """List all context grounding indexes.

    \b
    Examples:
        uipath context-grounding list --folder-path "Shared"
    """
    client = ServiceCommandBase.get_client(ctx)
    return client.context_grounding.list_indexes(
        folder_path=folder_path,
        folder_key=folder_key,
    )


@context_grounding.command(name="retrieve")
@click.option("--index-name", help="Name of the index to retrieve")
@click.option("--index-id", help="ID of the index to retrieve (ephemeral indexes only)")
@common_service_options
@service_command
def retrieve_index(
    ctx: click.Context,
    index_name: Optional[str],
    index_id: Optional[str],
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Retrieve a context grounding index.

    \b
    Two ways to specify the index:
        Regular index:   --index-name + --folder-path
        Ephemeral index: --index-id

    \b
    Examples:
        uipath context-grounding retrieve --index-name my-index --folder-path "Shared"
        uipath context-grounding retrieve --index-id abc-123-def-456 --format json
    """
    from httpx import HTTPStatusError

    if not index_name and not index_id:
        raise click.UsageError("Either --index-name or --index-id must be provided.")
    if index_name and index_id:
        raise click.UsageError("Provide either --index-name or --index-id, not both.")

    client = ServiceCommandBase.get_client(ctx)

    if index_id:
        from uipath.platform.context_grounding import ContextGroundingIndex

        raw = client.context_grounding.retrieve_by_id(
            index_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        return ContextGroundingIndex(**raw)

    assert index_name is not None  # validated above
    name = index_name
    try:
        return client.context_grounding.retrieve(
            name=name,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except LookupError:
        handle_not_found_error("Index", name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("Index", name, e)
        raise


@context_grounding.command(name="create")
@click.option("--index-name", required=True, help="Name of the index to create")
@click.option(
    "--source-file",
    type=click.Path(exists=True),
    help="JSON file with connection source configuration (Google Drive, OneDrive, Dropbox, Confluence)",
)
@click.option(
    "--bucket-source",
    help="Bucket name for bucket-backed indexes",
)
@click.option("--description", default="", help="Description of the index")
@click.option(
    "--extraction-strategy",
    type=click.Choice(["LLMV4", "NativeV1"]),
    default="LLMV4",
    help="Extraction strategy (default: LLMV4)",
)
@click.option("--file-type", help="File type filter (e.g., 'pdf', 'txt')")
@common_service_options
@service_command
def create_index(
    ctx: click.Context,
    index_name: str,
    source_file: Optional[str],
    bucket_source: Optional[str],
    description: str,
    extraction_strategy: str,
    file_type: Optional[str],
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Create a new context grounding index (persistent).

    The created index lives in an Orchestrator folder. Ingestion must be
    triggered separately after creation.

    \b
    Two ways to specify the data source:
        --bucket-source   Bucket name for bucket-backed indexes
        --source-file     JSON file for connections (use 'source-schema' to see formats)

    \b
    Examples:
        uipath context-grounding create --index-name my-index --bucket-source my-bucket
        uipath context-grounding create --index-name my-index --source-file config.json
    """
    if source_file and bucket_source:
        raise click.UsageError(
            "Cannot use both --source-file and --bucket-source. Choose one."
        )
    if not source_file and not bucket_source:
        raise click.UsageError(
            "Either --source-file or --bucket-source must be provided."
        )

    source: Any
    if source_file:
        from pydantic import TypeAdapter

        from uipath.platform.context_grounding import BucketSourceConfig, SourceConfig

        with open(source_file) as f:
            source_data = json_module.load(f)

        source = TypeAdapter(SourceConfig).validate_python(source_data)
    else:
        from uipath.platform.context_grounding import BucketSourceConfig

        assert bucket_source is not None  # validated above
        source = BucketSourceConfig(
            bucket_name=bucket_source,
            folder_path=folder_path or "",
            file_type=file_type,
        )

    client = ServiceCommandBase.get_client(ctx)
    result = client.context_grounding.create_index(
        name=index_name,
        source=source,
        description=description,
        extraction_strategy=extraction_strategy,
        folder_path=folder_path,
        folder_key=folder_key,
    )
    return result


_SOURCE_TYPES = {
    "google_drive": "GoogleDriveSourceConfig",
    "onedrive": "OneDriveSourceConfig",
    "dropbox": "DropboxSourceConfig",
    "confluence": "ConfluenceSourceConfig",
}


@context_grounding.command(name="source-schema")
@click.option(
    "--type",
    "source_type",
    type=click.Choice(list(_SOURCE_TYPES.keys())),
    help="Show schema for a specific source type (omit to show all)",
)
def source_schema(source_type: Optional[str]) -> None:
    """Show JSON source file formats for connection-backed indexes.

    Use this to see the required fields for --source-file when creating
    an index backed by Google Drive, OneDrive, Dropbox, or Confluence.

    \b
    Examples:
        uipath context-grounding source-schema --type google_drive
    """
    import json

    from uipath.platform.context_grounding import context_grounding_payloads as payloads

    types_to_show = (
        {source_type: _SOURCE_TYPES[source_type]} if source_type else _SOURCE_TYPES
    )

    for type_key, class_name in types_to_show.items():
        cls = getattr(payloads, class_name)
        schema = cls.model_json_schema()
        required = schema.get("required", [])
        props = schema.get("properties", {})
        example = {}
        for field_name, info in props.items():
            if field_name in required:
                default = info.get("default")
                example[field_name] = (
                    default
                    if default is not None
                    else f"<{info.get('description', field_name)}>"
                )
        click.echo(f"\n{type_key}:", err=False)
        click.echo(json.dumps(example, indent=2), err=False)

    click.echo("", err=False)


@context_grounding.command(name="create-ephemeral")
@click.option(
    "--usage",
    required=True,
    type=click.Choice(["DeepRAG", "BatchRAG"]),
    help="Task type for the ephemeral index",
)
@click.option(
    "--files",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Local file paths to upload as attachments (repeatable)",
)
@common_service_options
@service_command
def create_ephemeral(
    ctx: click.Context,
    usage: str,
    files: tuple[str, ...],
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Create an ephemeral index from local files (temporary).

    Uploads files as attachments and creates a temporary index. Reference it
    in other commands with --index-id (no folder, no name). Ingestion starts
    automatically. Poll with 'retrieve --index-id <id>' until
    lastIngestionStatus is Successful before starting a task.

    \b
    Supported file types:
        DeepRAG:  PDF, TXT
        BatchRAG: CSV

    \b
    Examples:
        uipath context-grounding create-ephemeral --usage DeepRAG --files doc1.pdf --files doc2.pdf
        uipath context-grounding create-ephemeral --usage BatchRAG --files data.csv
    """
    from pathlib import Path

    from uipath.platform.context_grounding import EphemeralIndexUsage

    allowed_extensions = {
        "DeepRAG": {".pdf", ".txt"},
        "BatchRAG": {".csv"},
    }
    allowed = allowed_extensions[usage]
    for file_path in files:
        ext = Path(file_path).suffix.lower()
        if ext not in allowed:
            raise click.UsageError(
                f"File '{Path(file_path).name}' has unsupported extension '{ext}' for {usage}. "
                f"Supported: {', '.join(sorted(allowed))}"
            )

    client = ServiceCommandBase.get_client(ctx)

    attachment_ids = []
    for file_path in files:
        file_name = Path(file_path).name
        click.echo(f"Uploading '{file_name}'...", err=True)
        attachment_id = client.attachments.upload(
            name=file_name,
            source_path=file_path,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        attachment_ids.append(str(attachment_id))
        click.echo(f"Uploaded '{file_name}' (ID: {attachment_id})", err=True)

    click.echo("Creating ephemeral index...", err=True)
    index = client.context_grounding.create_ephemeral_index(
        usage=EphemeralIndexUsage(usage),
        attachments=attachment_ids,
    )
    click.echo(f"Ephemeral index created: {index.id}", err=True)

    return index


@context_grounding.command(name="delete")
@click.option("--index-name", required=True, help="Name of the index to delete")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be deleted without deleting"
)
@common_service_options
@service_command
def delete_index(
    ctx: click.Context,
    index_name: str,
    confirm: bool,
    dry_run: bool,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Delete a context grounding index.

    \b
    Examples:
        uipath context-grounding delete --index-name my-index --confirm
        uipath context-grounding delete --index-name my-index --dry-run
    """
    from httpx import HTTPStatusError

    client = ServiceCommandBase.get_client(ctx)

    # First retrieve to verify index exists
    try:
        client.context_grounding.retrieve(
            name=index_name,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except LookupError:
        handle_not_found_error("Index", index_name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("Index", index_name, e)
        raise

    # Handle dry-run
    if dry_run:
        click.echo(f"Would delete index '{index_name}'", err=True)
        return

    # Handle confirmation
    if not confirm:
        if not click.confirm(f"Delete index '{index_name}'?"):
            click.echo("Deletion cancelled.")
            return

    # Perform delete
    client.context_grounding.delete_by_name(
        name=index_name,
        folder_path=folder_path,
        folder_key=folder_key,
    )

    click.echo(f"Deleted index '{index_name}'", err=True)


@context_grounding.command(name="ingest")
@click.option("--index-name", required=True, help="Name of the index to ingest")
@common_service_options
@service_command
def ingest_index(
    ctx: click.Context,
    index_name: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> None:
    """Trigger ingestion on a context grounding index.

    Ingestion runs asynchronously. Use 'retrieve' to poll lastIngestionStatus
    until it reaches Successful or Failed.

    \b
    Examples:
        uipath context-grounding ingest --index-name my-index --folder-path "Shared"
    """
    client = ServiceCommandBase.get_client(ctx)
    client.context_grounding.ingest_by_name(
        name=index_name,
        folder_path=folder_path,
        folder_key=folder_key,
    )

    click.echo(f"Ingestion triggered for index '{index_name}'", err=True)


@context_grounding.command(name="search")
@click.option("--index-name", required=True, help="Name of the index to search")
@click.option("--query", required=True, help="Search query in natural language")
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=10,
    help="Maximum number of results (default: 10)",
)
@click.option(
    "--threshold",
    type=click.FloatRange(min=0.0, max=1.0),
    default=0.0,
    help="Minimum similarity threshold (default: 0.0)",
)
@click.option(
    "--search-mode",
    type=click.Choice(["Auto", "Semantic"]),
    default="Auto",
    help="Search mode (default: Auto)",
)
@common_service_options
@service_command
def search_index(
    ctx: click.Context,
    index_name: str,
    query: str,
    limit: int,
    threshold: float,
    search_mode: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Search a context grounding index (regular indexes only).

    \b
    Examples:
        uipath context-grounding search --index-name my-index --query "What is the revenue?"
        uipath context-grounding search --index-name my-index --query "results" --limit 5
    """
    from uipath.platform.context_grounding import SearchMode

    client = ServiceCommandBase.get_client(ctx)
    return client.context_grounding.unified_search(
        name=index_name,
        query=query,
        number_of_results=limit,
        threshold=threshold,
        search_mode=SearchMode(search_mode),
        folder_path=folder_path,
        folder_key=folder_key,
    )


# --- Deep RAG nested group ---


@click.group(name="deep-rag")
def deep_rag() -> None:
    """Manage Deep RAG tasks.

    Deep RAG performs multi-document research and synthesis on context
    grounding indexes.

    \b
    Examples:
        uipath context-grounding deep-rag start --help
    """
    pass


@deep_rag.command(name="start")
@click.option("--index-name", help="Name of the context grounding index")
@click.option(
    "--index-id", help="ID of the context grounding index (ephemeral indexes only)"
)
@click.option("--task-name", required=True, help="Name for the Deep RAG task")
@click.option("--prompt", required=True, help="Task prompt describing what to research")
@click.option(
    "--glob-pattern",
    default="**",
    help="Glob pattern to filter files in the index (default: **)",
)
@click.option(
    "--citation-mode",
    type=click.Choice(["Skip", "Inline"]),
    default="Skip",
    help="Citation mode (default: Skip)",
)
@common_service_options
@service_command
def start_deep_rag(
    ctx: click.Context,
    index_name: Optional[str],
    index_id: Optional[str],
    task_name: str,
    prompt: str,
    glob_pattern: str,
    citation_mode: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Start a Deep RAG task on an index.

    \b
    Two ways to specify the index:
        Regular index:   --index-name + --folder-path
        Ephemeral index: --index-id

    \b
    Examples:
        uipath context-grounding deep-rag start --index-name my-index --folder-path Shared --task-name my-task --prompt "Summarize"
        uipath context-grounding deep-rag start --index-id abc-123 --task-name my-task --prompt "Summarize"
    """
    from uipath.platform.context_grounding import CitationMode

    if not index_name and not index_id:
        raise click.UsageError("Either --index-name or --index-id must be provided.")
    if index_name and index_id:
        raise click.UsageError("Provide either --index-name or --index-id, not both.")

    client = ServiceCommandBase.get_client(ctx)
    result = client.context_grounding.start_deep_rag(
        name=task_name,
        prompt=prompt,
        index_name=index_name,
        index_id=index_id,
        glob_pattern=glob_pattern,
        citation_mode=CitationMode(citation_mode),
        folder_path=folder_path,
        folder_key=folder_key,
    )

    click.echo(f"Deep RAG task started: {result.id}", err=True)

    return result


@deep_rag.command(name="retrieve")
@click.option("--task-id", required=True, help="ID of the Deep RAG task")
@common_service_options
@service_command
def retrieve_deep_rag(
    ctx: click.Context,
    task_id: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Retrieve a Deep RAG task result (status, summary, citations).

    \b
    Examples:
        uipath context-grounding deep-rag retrieve --task-id abc-123-def-456
    """
    client = ServiceCommandBase.get_client(ctx)
    return client.context_grounding.retrieve_deep_rag(id=task_id)


context_grounding.add_command(deep_rag)


# --- Batch Transform nested group ---


@click.group(name="batch-transform")
def batch_transform() -> None:
    """Manage Batch Transform tasks.

    Batch Transform processes and transforms CSV files from context
    grounding indexes.

    \b
    Examples:
        uipath context-grounding batch-transform start --help
    """
    pass


@batch_transform.command(name="start")
@click.option("--index-name", help="Name of the context grounding index")
@click.option(
    "--index-id", help="ID of the context grounding index (ephemeral indexes only)"
)
@click.option("--task-name", required=True, help="Name for the Batch Transform task")
@click.option("--prompt", required=True, help="Task prompt describing what to process")
@click.option(
    "--columns-file",
    required=True,
    type=click.Path(exists=True),
    help="JSON file defining output columns (see format above)",
)
@click.option("--target-file", help="Specific file name to target in the index")
@click.option(
    "--prefix",
    help="Storage bucket folder path prefix for filtering files",
)
@click.option(
    "--web-search",
    is_flag=True,
    help="Enable web search grounding",
)
@common_service_options
@service_command
def start_batch_transform(
    ctx: click.Context,
    index_name: Optional[str],
    index_id: Optional[str],
    task_name: str,
    prompt: str,
    columns_file: str,
    target_file: Optional[str],
    prefix: Optional[str],
    web_search: bool,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Start a Batch Transform task on an index.

    The index must contain CSV files. Only one file is processed per task.

    \b
    Two ways to specify the index:
        Regular index:   --index-name + --folder-path
        Ephemeral index: --index-id

    \b
    --columns-file is a JSON array defining output columns:
        [
          {"name": "entity", "description": "Extracted entity name"},
          {"name": "category", "description": "Entity category"}
        ]

    \b
    Examples:
        uipath context-grounding batch-transform start --index-name my-index --task-name my-task --prompt "Extract" --columns-file cols.json
        uipath context-grounding batch-transform start --index-id abc-123 --task-name my-task --prompt "Extract" --columns-file cols.json
    """
    from uipath.platform.context_grounding import BatchTransformOutputColumn

    if not index_name and not index_id:
        raise click.UsageError("Either --index-name or --index-id must be provided.")
    if index_name and index_id:
        raise click.UsageError("Provide either --index-name or --index-id, not both.")

    with open(columns_file) as f:
        columns_data = json_module.load(f)

    output_columns = [BatchTransformOutputColumn(**col) for col in columns_data]

    client = ServiceCommandBase.get_client(ctx)
    result = client.context_grounding.start_batch_transform(
        name=task_name,
        prompt=prompt,
        index_name=index_name,
        index_id=index_id,
        output_columns=output_columns,
        storage_bucket_folder_path_prefix=prefix,
        target_file_name=target_file,
        enable_web_search_grounding=web_search,
        folder_path=folder_path,
        folder_key=folder_key,
    )

    click.echo(f"Batch Transform task started: {result.id}", err=True)

    return result


@batch_transform.command(name="retrieve")
@click.option("--task-id", required=True, help="ID of the Batch Transform task")
@common_service_options
@service_command
def retrieve_batch_transform(
    ctx: click.Context,
    task_id: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Retrieve a Batch Transform task status.

    \b
    Examples:
        uipath context-grounding batch-transform retrieve --task-id abc-123-def-456
    """
    client = ServiceCommandBase.get_client(ctx)
    return client.context_grounding.retrieve_batch_transform(id=task_id)


@batch_transform.command(name="download")
@click.option("--task-id", required=True, help="ID of the Batch Transform task")
@click.option(
    "--output-file",
    required=True,
    type=click.Path(),
    help="Local destination path for the result file",
)
@common_service_options
@service_command
def download_batch_transform(
    ctx: click.Context,
    task_id: str,
    output_file: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> None:
    """Download a Batch Transform result file.

    \b
    Examples:
        uipath context-grounding batch-transform download --task-id abc-123 --output-file result.csv
    """
    client = ServiceCommandBase.get_client(ctx)
    client.context_grounding.download_batch_transform_result(
        id=task_id,
        destination_path=output_file,
    )

    click.echo(f"Downloaded to '{output_file}'", err=True)


context_grounding.add_command(batch_transform)


def __getattr__(name: str) -> click.Group:
    """Allow lazy loading with hyphenated command name."""
    if name == "context-grounding":
        return context_grounding
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
