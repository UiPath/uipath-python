"""Buckets service commands for UiPath CLI.

Buckets are cloud storage containers for files used by automation processes.
Similar to AWS S3 or Azure Blob Storage.
"""
# ruff: noqa: D301 - Using regular """ strings (not r""") for Click \b formatting

from itertools import islice

import click

from .._utils._context import get_cli_context
from .._utils._service_base import (
    ServiceCommandBase,
    common_service_options,
    handle_not_found_error,
    service_command,
)


@click.group()
def buckets():
    """Manage UiPath storage buckets.

    Buckets are cloud storage containers for files used by automation processes.

    \b
    Examples:
        # List all buckets
        uipath buckets list --folder-path "Shared"

        # Create a bucket
        uipath buckets create my-bucket --description "Data storage"

        # Download file from bucket
        uipath buckets download my-bucket data.csv ./local.csv

        # Upload file to bucket
        uipath buckets upload my-bucket ./local.csv remote/data.csv

        # Delete bucket
        uipath buckets delete my-bucket --confirm
    """
    pass


@buckets.command(name="list")
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    help="Maximum number of items to return",
)
@click.option(
    "--offset",
    type=click.IntRange(min=0),
    default=0,
    help="Number of items to skip",
)
@click.option(
    "--all", "fetch_all", is_flag=True, help="Fetch all items (auto-paginate)"
)
@common_service_options
@service_command
def list_buckets(
    ctx, folder_path, folder_key, format, output, limit, offset, fetch_all
):
    """List all buckets in a folder.

    The SDK provides an auto-paginating iterator over all buckets.
    The CLI applies client-side slicing using --limit and --offset to control
    which results are displayed.

    \b
    Examples:
        uipath buckets list
        uipath buckets list --folder-path "Production"
        uipath buckets list --limit 10 --format json
        uipath buckets list --all  # Fetch all buckets with auto-pagination
    """
    client = ServiceCommandBase.get_client(ctx)
    cli_ctx = get_cli_context(ctx)

    # The SDK list() method returns an iterator that auto-paginates
    # We consume it and return the results
    buckets_iterator = client.buckets.list(
        folder_path=folder_path or cli_ctx.default_folder,
        folder_key=folder_key,
    )

    # Handle limit=0 edge case: return empty list immediately
    if not fetch_all and limit == 0:
        return []

    # Use itertools.islice for precise, efficient iterator slicing
    # This avoids the truthiness bug (limit=0) and improves performance
    start = offset
    stop = None if fetch_all or limit is None else start + limit
    return list(islice(buckets_iterator, start, stop))


@buckets.command()
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
    cli_ctx = get_cli_context(ctx)

    try:
        bucket = client.buckets.retrieve(
            name=name,
            key=key,
            folder_path=folder_path or cli_ctx.default_folder,
            folder_key=folder_key,
        )
    except LookupError:
        handle_not_found_error(name or key)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error(name or key, e)
        raise

    return bucket


@buckets.command()
@click.argument("name")
@click.option("--description", help="Bucket description")
@common_service_options
@service_command
def create(ctx, name, description, folder_path, folder_key, format, output):
    """Create a new bucket.

    \b
    Arguments:
        NAME: Name of the bucket to create

    \b
    Examples:
        uipath buckets create my-bucket
        uipath buckets create reports --description "Monthly reports storage"
    """
    client = ServiceCommandBase.get_client(ctx)
    cli_ctx = get_cli_context(ctx)

    bucket = client.buckets.create(
        name=name,
        description=description,
        folder_path=folder_path or cli_ctx.default_folder,
        folder_key=folder_key,
    )

    click.echo(f"Created bucket '{name}'", err=True)
    return bucket


@buckets.command()
@click.argument("name")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
@common_service_options
@service_command
def delete(ctx, name, confirm, dry_run, folder_path, folder_key, format, output):
    """Delete a bucket.

    \b
    Arguments:
        NAME: Name of the bucket to delete

    \b
    Examples:
        uipath buckets delete old-bucket --confirm
        uipath buckets delete test-bucket --dry-run
    """
    from httpx import HTTPStatusError

    client = ServiceCommandBase.get_client(ctx)
    cli_ctx = get_cli_context(ctx)

    # First retrieve to show what will be deleted
    try:
        bucket = client.buckets.retrieve(
            name=name,
            folder_path=folder_path or cli_ctx.default_folder,
            folder_key=folder_key,
        )
    except LookupError:
        handle_not_found_error(name)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            handle_not_found_error(name, e)
        raise

    if dry_run:
        click.echo(f"Would delete bucket: {bucket.name} (ID: {bucket.id})", err=True)
        return

    if not confirm:
        if not click.confirm(f"Delete bucket '{bucket.name}'?"):
            click.echo("Aborted", err=True)
            return

    # Use resource pattern: bucket.delete() instead of client.buckets.delete()
    bucket.delete()

    click.echo(f"Deleted bucket '{name}'", err=True)


@buckets.command()
@click.argument("bucket_name")
@click.argument("remote_path")
@click.argument("local_path", type=click.Path())
@common_service_options
@service_command
def download(
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
        uipath buckets download my-bucket data.csv ./downloads/data.csv
        uipath buckets download reports monthly/report.pdf ./report.pdf
    """
    client = ServiceCommandBase.get_client(ctx)
    cli_ctx = get_cli_context(ctx)

    # Simple activity messages instead of fake progress bar
    click.echo(f"Downloading {remote_path}...", err=True)
    client.buckets.download(
        name=bucket_name,
        blob_file_path=remote_path,
        destination_path=local_path,
        folder_path=folder_path or cli_ctx.default_folder,
        folder_key=folder_key,
    )

    click.echo(f"Downloaded to {local_path}", err=True)


@buckets.command()
@click.argument("bucket_name")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_path")
@common_service_options
@service_command
def upload(
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
        uipath buckets upload my-bucket ./data.csv remote/data.csv
        uipath buckets upload reports ./report.pdf monthly/report.pdf
    """
    client = ServiceCommandBase.get_client(ctx)
    cli_ctx = get_cli_context(ctx)

    # Simple activity messages instead of fake progress bar
    click.echo(f"Uploading {local_path}...", err=True)
    client.buckets.upload(
        name=bucket_name,
        source_path=local_path,
        blob_file_path=remote_path,
        folder_path=folder_path or cli_ctx.default_folder,
        folder_key=folder_key,
    )

    click.echo(f"Uploaded to {remote_path}", err=True)
