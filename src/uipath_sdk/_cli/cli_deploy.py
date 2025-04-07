# type: ignore
import click

from uipath_sdk._cli.cli_pack import pack
from uipath_sdk._cli.cli_publish import publish


@click.command()
@click.argument("root", type=str, default="./")
def deploy(root):
    ctx = click.get_current_context()
    ctx.invoke(pack, root=root)
    ctx.invoke(publish)
