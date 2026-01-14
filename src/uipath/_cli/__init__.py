import importlib.metadata
import os
import sys

import click
from dotenv import load_dotenv

from uipath._cli._utils._context import CliContext
from uipath._cli.runtimes import load_runtime_factories
from uipath._utils._logs import setup_logging
from uipath._utils.constants import DOTENV_FILE
from uipath.functions import register_default_runtime_factory

# DO NOT ADD HEAVY IMPORTS HERE
#
# Every import at the top of this file runs on EVERY command.
# Yes, even `--version`. Yes, even `--help`.
#
# We spent hours getting startup from 1.7s → 0.5s.
# If you add `import pandas` here, I will find you.


def add_cwd_to_path():
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


def load_environment_variables():
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), DOTENV_FILE), override=True)


load_environment_variables()
add_cwd_to_path()
register_default_runtime_factory()
load_runtime_factories()


def _get_safe_version() -> str:
    """Get the version of the uipath package."""
    try:
        version = importlib.metadata.version("uipath")
        return version
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


class LazyGroup(click.Group):
    """Lazy-load commands only when invoked."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_commands = {
            "new": "cli_new",
            "init": "cli_init",
            "pack": "cli_pack",
            "publish": "cli_publish",
            "run": "cli_run",
            "deploy": "cli_deploy",
            "auth": "cli_auth",
            "invoke": "cli_invoke",
            "push": "cli_push",
            "pull": "cli_pull",
            "eval": "cli_eval",
            "dev": "cli_dev",
            "add": "cli_add",
            "register": "cli_register",
            "debug": "cli_debug",
            "buckets": "services.cli_buckets",
        }

    def list_commands(self, ctx):
        return sorted(self._lazy_commands.keys())

    def get_command(self, ctx, cmd_name):
        if cmd_name in self._lazy_commands:
            module_name = self._lazy_commands[cmd_name]
            mod = __import__(f"uipath._cli.{module_name}", fromlist=[cmd_name])
            return getattr(mod, cmd_name)
        return None


@click.command(cls=LazyGroup, invoke_without_command=True)
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

    setup_logging(should_debug=debug)

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
