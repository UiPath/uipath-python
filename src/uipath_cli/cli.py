# type: ignore
import click

from .cli_init import cli_init as init
from .cli_pack import cli_pack as pack


@click.group()
def cli() -> None:
    pass


cli.add_command(init)
cli.add_command(pack)

if __name__ == "__main__":
    cli()
