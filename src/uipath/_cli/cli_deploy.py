# type: ignore
import click

from .cli_pack import pack
from .cli_publish import publish


@click.command()
@click.option(
    "--tenant",
    "-t",
    "feed",
    flag_value="tenant",
    help="Whether to publish to the tenant package feed",
)
@click.option(
    "--my-workspace",
    "-w",
    "feed",
    flag_value="personal",
    help="Whether to publish to the personal workspace",
)
@click.option(
    "--folder",
    "-f",
    "folder",
    type=str,
    help="Folder name to publish to (skips interactive selection)",
)
@click.argument("root", type=str, default="./")
def deploy(root, feed, folder):
    """Pack and publish the project."""
    ctx = click.get_current_context()
    ctx.invoke(pack, root=root)
    ctx.invoke(publish, feed=feed, folder=folder)
