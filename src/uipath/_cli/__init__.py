import importlib.metadata
import sys

import click

from .cli_auth import auth as auth  # type: ignore
from .cli_deploy import deploy as deploy  # type: ignore
from .cli_init import init as init  # type: ignore
from .cli_invoke import invoke as invoke  # type: ignore
from .cli_new import new as new  # type: ignore
from .cli_pack import pack as pack  # type: ignore
from .cli_publish import publish as publish  # type: ignore
from .cli_run import run as run  # type: ignore


def _get_safe_version() -> str:
    """Get the version of the uipath package."""
    try:
        version = importlib.metadata.version("uipath")
        return version
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


@click.group(invoke_without_command=True)
@click.version_option(
    _get_safe_version(),
    prog_name="uipath",
    message="%(prog)s version %(version)s",
)
@click.option(
    "-lv",
    is_flag=True,
    help="Display the current version of uipath-langchain.",
)
@click.option(
    "-v",
    is_flag=True,
    help="Display the current version of uipath.",
)
def cli(lv: bool, v: bool) -> None:
    if lv:
        try:
            version = importlib.metadata.version("uipath-langchain")
            click.echo(f"uipath-langchain version {version}")
        except importlib.metadata.PackageNotFoundError:
            click.echo("uipath-langchain is not installed", err=True)
            sys.exit(1)
    if v:
        try:
            version = importlib.metadata.version("uipath")
            click.echo(f"uipath version {version}")
        except importlib.metadata.PackageNotFoundError:
            click.echo("uipath is not installed", err=True)
            sys.exit(1)


cli.add_command(new)
cli.add_command(init)
cli.add_command(pack)
cli.add_command(publish)
cli.add_command(run)
cli.add_command(deploy)
cli.add_command(auth)
cli.add_command(invoke)
