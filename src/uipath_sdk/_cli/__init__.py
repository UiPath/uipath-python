import click

from .cli_init import init as init  # type: ignore
from .cli_pack import pack as pack  # type: ignore
from .cli_publish import publish as publish  # type: ignore


@click.group()
def cli() -> None:
    pass


cli.add_command(init)
cli.add_command(pack)
cli.add_command(publish)
