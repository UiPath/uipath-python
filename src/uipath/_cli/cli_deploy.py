# type: ignore
import click

from .cli_pack import pack
from .cli_publish import publish


@click.command()
@click.argument("root", type=str, default="./")
def deploy(root):
    ctx = click.get_current_context()
    ctx.invoke(pack, root=root)
    ctx.invoke(publish)
