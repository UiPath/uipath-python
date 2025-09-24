import importlib.metadata
import sys

import click

from ._utils._common import load_environment_variables
from .cli_auth import auth as auth
from .cli_deploy import deploy as deploy  # type: ignore
from .cli_dev import dev as dev
from .cli_eval import eval as eval  # type: ignore
from .cli_init import generate_agents_md as generate_agents_md  # type: ignore
from .cli_init import init as init  # type: ignore
from .cli_invoke import invoke as invoke  # type: ignore
from .cli_new import new as new  # type: ignore
from .cli_pack import pack as pack  # type: ignore
from .cli_publish import publish as publish  # type: ignore
from .cli_pull import pull as pull  # type: ignore
from .cli_push import push as push  # type: ignore
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
    load_environment_variables()
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
cli.add_command(push)
cli.add_command(pull)
cli.add_command(eval)
cli.add_command(dev)
cli.add_command(run, name="debug")
