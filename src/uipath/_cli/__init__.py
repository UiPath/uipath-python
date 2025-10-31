import importlib.metadata
import sys

import click

from ._utils._common import add_cwd_to_path, load_environment_variables
from ._utils._context import CliContext
from .cli_add import add as add
from .cli_auth import auth as auth
from .cli_debug import debug as debug  # type: ignore
from .cli_deploy import deploy as deploy  # type: ignore
from .cli_dev import dev as dev
from .cli_eval import eval as eval
from .cli_init import init as init  # type: ignore
from .cli_invoke import invoke as invoke  # type: ignore
from .cli_new import new as new  # type: ignore
from .cli_pack import pack as pack  # type: ignore
from .cli_publish import publish as publish  # type: ignore
from .cli_pull import pull as pull  # type: ignore
from .cli_push import push as push  # type: ignore
from .cli_register import register as register  # type: ignore
from .cli_run import run as run  # type: ignore

load_environment_variables()
add_cwd_to_path()


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
@click.option(
    "--format",
    type=click.Choice(["json", "table", "csv"]),
    default="table",
    help="Output format for commands",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging and show stack traces",
)
@click.pass_context
def cli(
    ctx: click.Context,
    lv: bool,
    v: bool,
    format: str,
    debug: bool,
) -> None:
    """UiPath CLI - Automate everything.

    \b
    Examples:
        uipath new my-project
        uipath dev
        uipath deploy
        uipath buckets list --folder-path "Shared"
    """  # noqa: D301
    ctx.obj = CliContext(
        output_format=format,
        debug=debug,
    )

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

    # Show help if no command was provided (matches docker, kubectl, git behavior)
    if ctx.invoked_subcommand is None and not lv and not v:
        click.echo(ctx.get_help())


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
cli.add_command(add)
cli.add_command(register)
cli.add_command(debug)

from .services import register_service_commands  # noqa: E402

register_service_commands(cli)
