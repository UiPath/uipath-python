import click

from .cli_init import cli_init as init  # type: ignore
from .cli_pack import cli_pack as pack  # type: ignore


@click.group()
def cli() -> None:
    pass


cli.add_command(init)
cli.add_command(pack)
