"""Assets service commands for UiPath CLI.

Assets are key-value pairs stored in Orchestrator that can be used to store
configuration data, credentials, and other settings used by automation processes.
"""

import click

from .._utils._service_base import (
    ServiceCommandBase,
    common_service_options,
    service_command,
)


@click.group()
def assets():
    r"""Manage UiPath assets.

    Assets are key-value pairs that store configuration data, credentials,
    and settings used by automation processes.

    \b
    Examples:
        # List all assets in a folder
        uipath assets list --folder-path "Shared"

        # List with filter
        uipath assets list --filter "ValueType eq 'Text'"

        # List with ordering
        uipath assets list --orderby "Name asc"
    """
    pass


@assets.command(name="list")
@click.option("--filter", "filter_", help="OData $filter expression")
@click.option("--orderby", help="OData $orderby expression")
@click.option(
    "--top",
    type=click.IntRange(min=1, max=1000),
    default=100,
    help="Maximum number of items to return (default: 100, max: 1000)",
)
@click.option(
    "--skip",
    type=click.IntRange(min=0),
    default=0,
    help="Number of items to skip",
)
@common_service_options
@service_command
def list_assets(
    ctx,
    filter_,
    orderby,
    top,
    skip,
    folder_path,
    folder_key,
    format,
    output,
):
    r"""List assets in a folder.

    \b
    Examples:
        uipath assets list
        uipath assets list --folder-path "Shared"
        uipath assets list --filter "ValueType eq 'Text'"
        uipath assets list --filter "Name eq 'MyAsset'"
        uipath assets list --orderby "Name asc"
        uipath assets list --top 50 --skip 100
    """
    client = ServiceCommandBase.get_client(ctx)

    result = client.assets.list(
        folder_path=folder_path,
        folder_key=folder_key,
        filter=filter_,
        orderby=orderby,
        top=top,
        skip=skip,
    )

    return list(result.items)
