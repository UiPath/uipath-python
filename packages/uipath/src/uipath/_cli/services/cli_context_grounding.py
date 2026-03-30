"""Context Grounding service commands for UiPath CLI.

Context Grounding provides semantic search over indexed document collections,
enabling RAG (Retrieval-Augmented Generation) for automation processes.

Commands:
    list      - List all indexes in a folder
    retrieve  - Get details of a specific index by name
    search    - Perform semantic search against an index
    ingest    - Trigger re-ingestion of an index
    delete    - Delete an index by name

Note:
    create_index is intentionally not exposed here — its source configuration
    (bucket, Google Drive, OneDrive, Dropbox, Confluence) is too complex to
    express cleanly as CLI flags. Use the Python SDK directly for index creation.
"""
# ruff: noqa: D301 - Using regular """ strings (not r""") for Click \b formatting

from typing import Any, NoReturn, Optional

import click
from httpx import HTTPStatusError

from .._utils._service_base import (
    ServiceCommandBase,
    common_service_options,
    handle_not_found_error,
    service_command,
)

# The SDK raises a bare Exception with this message when an index name doesn't exist.
_INDEX_NOT_FOUND_MSG = "ContextGroundingIndex not found"


def _handle_retrieve_error(index_name: str, e: Exception) -> NoReturn:
    """Convert a retrieve() exception to a clean ClickException.

    Mirrors the pattern used in cli_buckets.py:
    - bare Exception with the SDK's not-found message → structured not-found error
    - HTTPStatusError 404 → structured not-found error
    - anything else → re-raise so service_command's handler deals with it
    """
    if isinstance(e, HTTPStatusError):
        if e.response.status_code == 404:
            handle_not_found_error("Index", index_name, e)
        raise e
    if _INDEX_NOT_FOUND_MSG.lower() in str(e).lower():
        handle_not_found_error("Index", index_name)
    raise click.ClickException(str(e)) from e


@click.group(name="context-grounding")
def context_grounding() -> None:
    """Manage UiPath Context Grounding indexes and perform semantic search.

    Context Grounding indexes documents from storage buckets or cloud drives
    and makes them searchable via natural language queries (RAG).

    \b
    Commands:
        list      - List all indexes in a folder
        retrieve  - Get details of a specific index
        search    - Query an index with natural language
        ingest    - Trigger re-ingestion of an index
        delete    - Delete an index

    \b
    Examples:
        uipath context-grounding list --folder-path "Shared"
        uipath context-grounding retrieve --index "my-index" --folder-path "Shared"
        uipath context-grounding search "how to process invoices" --index "my-index" --folder-path "Shared"
        uipath context-grounding search "payment terms" --index "my-index" --folder-path "Shared" --limit 5
        uipath context-grounding ingest --index "my-index" --folder-path "Shared"
        uipath context-grounding delete --index "my-index" --folder-path "Shared" --confirm

    \b
    Folder context:
        Set UIPATH_FOLDER_PATH to avoid passing --folder-path on every command:
        export UIPATH_FOLDER_PATH="Shared"
    """
    pass


@context_grounding.command("list")
@common_service_options
@service_command
def list_indexes(
    ctx: click.Context,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """List all context grounding indexes in a folder.

    \b
    Examples:
        uipath context-grounding list --folder-path "Shared"
        uipath context-grounding list --folder-path "Shared" --format json
    """
    client = ServiceCommandBase.get_client(ctx)
    results = client.context_grounding.list(
        folder_path=folder_path,
        folder_key=folder_key,
    )

    # Table format: project to key fields for readability.
    # JSON/CSV: return full objects so nothing is lost for scripting.
    fmt = format or "table"
    if fmt == "table":
        return [
            {
                "name": ix.name,
                "last_ingestion_status": ix.last_ingestion_status,
                "last_ingested": ix.last_ingested,
                "description": ix.description,
            }
            for ix in results
        ]

    return results


@context_grounding.command("retrieve")
@click.option(
    "--index", "index_name", required=True, help="Name of the index to retrieve."
)
@common_service_options
@service_command
def retrieve(
    ctx: click.Context,
    index_name: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Retrieve details of a context grounding index by name.

    \b
    Examples:
        uipath context-grounding retrieve --index "my-index" --folder-path "Shared"
        uipath context-grounding retrieve --index "my-index" --folder-path "Shared" --format json
    """
    client = ServiceCommandBase.get_client(ctx)

    try:
        return client.context_grounding.retrieve(
            name=index_name,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except Exception as e:
        _handle_retrieve_error(index_name, e)


@context_grounding.command("search")
@click.argument("query")
@click.option(
    "--index", "index_name", required=True, help="Name of the index to search."
)
@click.option(
    "--limit",
    "-n",
    "number_of_results",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Maximum number of results to return.",
)
@click.option(
    "--threshold",
    type=float,
    default=None,
    help="Minimum relevance score threshold (0.0–1.0). Results below this score are excluded.",
)
@common_service_options
@service_command
def search(
    ctx: click.Context,
    query: str,
    index_name: str,
    number_of_results: int,
    threshold: Optional[float],
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> Any:
    """Search an index with a natural language query.

    QUERY is the natural language search string.

    \b
    Examples:
        uipath context-grounding search "how to process invoices" --index "my-index" --folder-path "Shared"
        uipath context-grounding search "payment terms" --index "my-index" --folder-path "Shared" --limit 5
        uipath context-grounding search "invoice" --index "my-index" --folder-path "Shared" --threshold 0.7
        uipath context-grounding search "approval workflow" --index "my-index" --folder-path "Shared" --format json
        uipath context-grounding search "invoice policy" --index "my-index" --folder-path "Shared" -o results.json
    """
    from uipath.platform.errors import IngestionInProgressException

    client = ServiceCommandBase.get_client(ctx)

    try:
        results = client.context_grounding.search(
            name=index_name,
            query=query,
            number_of_results=number_of_results,
            threshold=threshold,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except IngestionInProgressException as e:
        raise click.ClickException(
            f"Index '{index_name}' is currently being ingested. "
            "Please wait for ingestion to complete and try again."
        ) from e
    except Exception as e:
        _handle_retrieve_error(index_name, e)

    if not results:
        click.echo("No results found.", err=True)
        return None

    # Table format: show only human-readable columns, truncate content.
    # JSON/CSV: return full objects so nothing is lost for scripting.
    fmt = format or "table"
    if fmt == "table":
        rows = []
        for r in results:
            content = r.content
            if len(content) > 120:
                content = content[:120] + "…"
            rows.append(
                {
                    "score": round(r.score, 3) if r.score is not None else None,
                    "source": r.source,
                    "page_number": r.page_number,
                    "content": content,
                }
            )
        return rows

    return results


@context_grounding.command("ingest")
@click.option(
    "--index", "index_name", required=True, help="Name of the index to re-ingest."
)
@common_service_options
@service_command
def ingest(
    ctx: click.Context,
    index_name: str,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> None:
    """Trigger re-ingestion of a context grounding index.

    \b
    Examples:
        uipath context-grounding ingest --index "my-index" --folder-path "Shared"
    """
    from uipath.platform.errors import IngestionInProgressException

    client = ServiceCommandBase.get_client(ctx)

    try:
        index = client.context_grounding.retrieve(
            name=index_name,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        if not index.id:
            raise click.ClickException(
                f"Index '{index_name}' has no ID and cannot be ingested."
            )
        if index.in_progress_ingestion():
            raise click.ClickException(
                f"Index '{index_name}' is already being ingested."
            )
        client.context_grounding.ingest_data(
            index=index,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except click.ClickException:
        raise
    except IngestionInProgressException as e:
        # Catches the 409 race condition from ingest_data() itself.
        raise click.ClickException(
            f"Index '{index_name}' is already being ingested."
        ) from e
    except Exception as e:
        _handle_retrieve_error(index_name, e)

    click.echo(f"Triggered ingestion for index '{index_name}'.", err=True)


@context_grounding.command("delete")
@click.option(
    "--index", "index_name", required=True, help="Name of the index to delete."
)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt.")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be deleted without deleting."
)
@common_service_options
@service_command
def delete(
    ctx: click.Context,
    index_name: str,
    confirm: bool,
    dry_run: bool,
    folder_path: Optional[str],
    folder_key: Optional[str],
    format: Optional[str],
    output: Optional[str],
) -> None:
    """Delete a context grounding index by name.

    \b
    Examples:
        uipath context-grounding delete --index "my-index" --folder-path "Shared" --confirm
        uipath context-grounding delete --index "my-index" --folder-path "Shared" --dry-run
    """
    client = ServiceCommandBase.get_client(ctx)

    # Resolve the index object first — surfaces not-found before prompting the user.
    try:
        index = client.context_grounding.retrieve(
            name=index_name,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except Exception as e:
        _handle_retrieve_error(index_name, e)

    if not index.id:
        raise click.ClickException(
            f"Index '{index_name}' has no ID and cannot be deleted."
        )

    # dry-run and confirmation after index is confirmed to exist and have an ID.
    if dry_run:
        click.echo(f"Would delete index '{index_name}'.", err=True)
        return

    if not confirm:
        if not click.confirm(f"Delete index '{index_name}'?"):
            click.echo("Deletion cancelled.")
            return

    try:
        client.context_grounding.delete_index(
            index=index,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except Exception as e:
        raise click.ClickException(f"Failed to delete index '{index_name}': {e}") from e

    click.echo(f"Deleted index '{index_name}'.", err=True)
