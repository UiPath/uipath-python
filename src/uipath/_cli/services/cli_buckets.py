"""Buckets service commands for UiPath CLI.

Buckets are cloud storage containers for files used by automation processes.
Similar to AWS S3 or Azure Blob Storage.

This module uses the Service CLI Generator to auto-generate standard CRUD commands
for bucket management, with custom implementations for file operations.

Architecture:
    - Auto-generated commands: list, create, delete, exists (via ServiceCLIGenerator)
    - Overridden command: retrieve (custom --name/--key dual-option support)
    - Manual nested group: files (with 6 custom file operation commands)
"""
# ruff: noqa: D301 - Using regular """ strings (not r""") for Click \b formatting

from itertools import islice

import click

from .._utils._service_base import (
    ServiceCommandBase,
    common_service_options,
    handle_not_found_error,
    service_command,
)
from .._utils._service_cli_generator import ServiceCLIGenerator
from ._buckets_metadata import BUCKETS_METADATA

_cli = click.Group()
generator = ServiceCLIGenerator(BUCKETS_METADATA)
buckets = generator.register(_cli)
buckets.help = """Manage UiPath storage buckets and files.

Buckets are cloud storage containers for files used by automation processes.

\b
Bucket Operations:
    list      - List all buckets
    create    - Create a new bucket
    delete    - Delete a bucket
    retrieve  - Get bucket details
    exists    - Check if bucket exists

\b
File Operations (use 'buckets files' subcommand):
    files list     - List files in a bucket
    files search   - Search files using glob patterns
    files upload   - Upload a file to a bucket
    files download - Download a file from a bucket
    files delete   - Delete a file from a bucket
    files exists   - Check if a file exists

\b
Examples:
    \b
    # Bucket operations with explicit folder
    uipath buckets list --folder-path "Shared"
    uipath buckets create my-bucket --description "Data storage"
    uipath buckets exists my-bucket
    uipath buckets delete my-bucket --confirm
    \b
    # Using environment variable for folder context
    export UIPATH_FOLDER_PATH="Shared"
    uipath buckets list
    uipath buckets create my-bucket --description "Data storage"
    \b
    # File operations
    uipath buckets files list my-bucket
    uipath buckets files search my-bucket "*.pdf"
    uipath buckets files upload my-bucket ./data.csv remote/data.csv
    uipath buckets files download my-bucket data.csv ./local.csv
    uipath buckets files delete my-bucket old-data.csv --confirm
    uipath buckets files exists my-bucket data.csv
"""


@click.command()
@click.option("--name", help="Bucket name")
@click.option("--key", help="Bucket key (UUID)")
@common_service_options
@service_command
def retrieve(ctx, name, key, folder_path, folder_key, format, output):
    """Retrieve a bucket by name or key.

    \b
    Examples:
        uipath buckets retrieve --name "my-bucket"
        uipath buckets retrieve --key "abc-123-def-456" --format json
    """
    from httpx import HTTPStatusError

    if not name and not key:
        raise click.UsageError("Either --name or --key must be provided")

    if name and key:
        raise click.UsageError("Provide either --name or --key, not both")

    client = ServiceCommandBase.get_client(ctx)

    try:
        bucket = client.buckets.retrieve(
            name=name,
            key=key,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except LookupError:
        handle_not_found_error("Bucket", name or key)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("Bucket", name or key, e)
        raise

    return bucket


generator.override_command(buckets, "retrieve", retrieve)


@click.command()
@click.argument("name")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be deleted without deleting"
)
@common_service_options
@service_command
def delete(ctx, name, confirm, dry_run, folder_path, folder_key, format, output):
    """Delete a bucket.

    \b
    Examples:
        uipath buckets delete my-bucket --confirm
        uipath buckets delete my-bucket --dry-run
    """
    from httpx import HTTPStatusError

    client = ServiceCommandBase.get_client(ctx)

    # First retrieve to verify bucket exists
    try:
        client.buckets.retrieve(
            name=name,
            folder_path=folder_path,
            folder_key=folder_key,
        )
    except LookupError:
        handle_not_found_error("Bucket", name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("Bucket", name, e)
        raise

    # Handle dry-run
    if dry_run:
        click.echo(f"Would delete bucket '{name}'", err=True)
        return

    # Handle confirmation
    if not confirm:
        if not click.confirm(f"Delete bucket '{name}'?"):
            click.echo("Deletion cancelled.")
            return

    # Perform delete
    client.buckets.delete(
        name=name,
        folder_path=folder_path,
        folder_key=folder_key,
    )

    click.echo(f"Deleted bucket '{name}'", err=True)


generator.override_command(buckets, "delete", delete)


@click.group()
def files():
    """Manage files within buckets.

    \b
    Examples:
        \b
        # List files in a bucket
        uipath buckets files list my-bucket
        \b
        # Search for files with glob pattern
        uipath buckets files search my-bucket "*.pdf"
        \b
        # Upload a file
        uipath buckets files upload my-bucket ./data.csv remote/data.csv
        \b
        # Download a file
        uipath buckets files download my-bucket data.csv ./local.csv
        \b
        # Delete a file
        uipath buckets files delete my-bucket old-data.csv --confirm
        \b
        # Check if file exists
        uipath buckets files exists my-bucket data.csv
    """
    pass


@files.command(name="list")
@click.argument("bucket_name")
@click.option("--prefix", default="", help="Filter files by prefix")
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    help="Maximum number of files to return",
)
@click.option(
    "--offset",
    type=click.IntRange(min=0),
    default=0,
    help="Number of files to skip",
)
@click.option(
    "--all", "fetch_all", is_flag=True, help="Fetch all files (auto-paginate)"
)
@common_service_options
@service_command
def list_files(
    ctx,
    bucket_name,
    prefix,
    limit,
    offset,
    fetch_all,
    folder_path,
    folder_key,
    format,
    output,
):
    """List files in a bucket.

    \b
    Arguments:
        BUCKET_NAME: Name of the bucket

    \b
    Examples:
        uipath buckets files list my-bucket
        uipath buckets files list my-bucket --prefix "data/"
        uipath buckets files list reports --limit 10 --format json
        uipath buckets files list my-bucket --all
    """
    from httpx import HTTPStatusError

    client = ServiceCommandBase.get_client(ctx)

    try:
        files_iterator = client.buckets.list_files(
            name=bucket_name,
            prefix=prefix,
            folder_path=folder_path,
            folder_key=folder_key,
        )

        if not fetch_all and limit == 0:
            return []

        start = offset
        stop = None if fetch_all or limit is None else start + limit
        return list(islice(files_iterator, start, stop))
    except LookupError:
        handle_not_found_error("Bucket", bucket_name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("Bucket", bucket_name, e)
        raise


@files.command(name="search")
@click.argument("bucket_name")
@click.argument("pattern")
@click.option("--prefix", default="", help="Directory path to search in")
@click.option(
    "--recursive/--no-recursive",
    default=False,
    help="Search subdirectories recursively",
)
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    help="Maximum number of files to return",
)
@common_service_options
@service_command
def search_files(
    ctx,
    bucket_name,
    pattern,
    prefix,
    recursive,
    limit,
    folder_path,
    folder_key,
    format,
    output,
):
    """Search for files using glob patterns.

    Uses the GetFiles API which supports glob patterns like *.pdf or data_*.csv.

    \b
    Arguments:
        BUCKET_NAME: Name of the bucket
        PATTERN: Glob pattern to match files (e.g., "*.pdf", "data_*.csv")

    \b
    Examples:
        uipath buckets files search my-bucket "*.pdf"
        uipath buckets files search reports "*.csv" --recursive
        uipath buckets files search my-bucket "data_*.json" --prefix "archive/"
    """
    from httpx import HTTPStatusError

    client = ServiceCommandBase.get_client(ctx)

    try:
        files_iterator = client.buckets.get_files(
            name=bucket_name,
            prefix=prefix,
            recursive=recursive,
            file_name_glob=pattern,
            folder_path=folder_path,
            folder_key=folder_key,
        )

        files = (
            list(files_iterator)
            if limit is None
            else list(islice(files_iterator, limit))
        )
        return files
    except LookupError:
        handle_not_found_error("Bucket", bucket_name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("Bucket", bucket_name, e)
        raise


@files.command(name="upload")
@click.argument("bucket_name")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_path")
@common_service_options
@service_command
def upload_file(
    ctx, bucket_name, local_path, remote_path, folder_path, folder_key, format, output
):
    """Upload a file to a bucket.

    \b
    Arguments:
        BUCKET_NAME: Name of the bucket
        LOCAL_PATH: Local file to upload
        REMOTE_PATH: Destination path in bucket

    \b
    Examples:
        uipath buckets files upload my-bucket ./data.csv remote/data.csv
        uipath buckets files upload reports ./report.pdf monthly/report.pdf
    """
    client = ServiceCommandBase.get_client(ctx)

    click.echo(f"Uploading {local_path}...", err=True)
    client.buckets.upload(
        name=bucket_name,
        source_path=local_path,
        blob_file_path=remote_path,
        folder_path=folder_path,
        folder_key=folder_key,
    )

    click.echo(f"Uploaded to {remote_path}", err=True)


@files.command(name="download")
@click.argument("bucket_name")
@click.argument("remote_path")
@click.argument("local_path", type=click.Path())
@common_service_options
@service_command
def download_file(
    ctx, bucket_name, remote_path, local_path, folder_path, folder_key, format, output
):
    """Download a file from a bucket.

    \b
    Arguments:
        BUCKET_NAME: Name of the bucket
        REMOTE_PATH: Path to file in bucket
        LOCAL_PATH: Local destination path

    \b
    Examples:
        uipath buckets files download my-bucket data.csv ./downloads/data.csv
        uipath buckets files download reports monthly/report.pdf ./report.pdf
    """
    client = ServiceCommandBase.get_client(ctx)

    click.echo(f"Downloading {remote_path}...", err=True)
    client.buckets.download(
        name=bucket_name,
        blob_file_path=remote_path,
        destination_path=local_path,
        folder_path=folder_path,
        folder_key=folder_key,
    )

    click.echo(f"Downloaded to {local_path}", err=True)


@files.command(name="delete")
@click.argument("bucket_name")
@click.argument("file_path")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
@common_service_options
@service_command
def delete_file(
    ctx,
    bucket_name,
    file_path,
    confirm,
    dry_run,
    folder_path,
    folder_key,
    format,
    output,
):
    """Delete a file from a bucket.

    \b
    Arguments:
        BUCKET_NAME: Name of the bucket
        FILE_PATH: Path to file in bucket

    \b
    Examples:
        uipath buckets files delete my-bucket old-data.csv --confirm
        uipath buckets files delete reports archive/old.pdf --dry-run
    """
    from httpx import HTTPStatusError

    client = ServiceCommandBase.get_client(ctx)

    if dry_run:
        click.echo(
            f"Would delete file: {file_path} from bucket {bucket_name}", err=True
        )
        return

    if not confirm:
        if not click.confirm(f"Delete file '{file_path}' from bucket '{bucket_name}'?"):
            click.echo("Aborted", err=True)
            return

    try:
        client.buckets.delete_file(
            name=bucket_name,
            blob_file_path=file_path,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        click.echo(f"Deleted file '{file_path}' from bucket '{bucket_name}'", err=True)
    except LookupError:
        handle_not_found_error("Bucket", bucket_name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("File or Bucket", f"{bucket_name}/{file_path}", e)
        raise


@files.command(name="exists")
@click.argument("bucket_name")
@click.argument("file_path")
@common_service_options
@service_command
def file_exists(ctx, bucket_name, file_path, folder_path, folder_key, format, output):
    """Check if a file exists in a bucket.

    \b
    Arguments:
        BUCKET_NAME: Name of the bucket
        FILE_PATH: Path to file in bucket

    \b
    Examples:
        uipath buckets files exists my-bucket data.csv
        uipath buckets files exists reports monthly/report.pdf
    """
    from httpx import HTTPStatusError

    client = ServiceCommandBase.get_client(ctx)

    try:
        file_exists_result = client.buckets.exists_file(
            name=bucket_name,
            blob_file_path=file_path,
            folder_path=folder_path,
            folder_key=folder_key,
        )

        if file_exists_result:
            click.echo(f"File '{file_path}' exists in bucket '{bucket_name}'", err=True)
            return {"exists": True, "bucket": bucket_name, "file": file_path}
        else:
            click.echo(
                f"File '{file_path}' does not exist in bucket '{bucket_name}'", err=True
            )
            return {"exists": False, "bucket": bucket_name, "file": file_path}
    except LookupError:
        handle_not_found_error("Bucket", bucket_name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error("Bucket", bucket_name, e)
        raise


generator.add_nested_group(buckets, "files", files)
