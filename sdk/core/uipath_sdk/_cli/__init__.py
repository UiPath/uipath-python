import click

from .cli_deploy import deploy as deploy  # type: ignore
from .cli_init import init as init  # type: ignore
from .cli_new import new as new  # type: ignore
from .cli_pack import pack as pack  # type: ignore
from .cli_publish import publish as publish  # type: ignore
from .cli_run import run as run  # type: ignore


@click.group()
def cli() -> None:
    pass


cli.add_command(new)
cli.add_command(init)
cli.add_command(pack)
cli.add_command(publish)
cli.add_command(run)
cli.add_command(deploy)
