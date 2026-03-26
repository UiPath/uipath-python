import importlib.metadata
import os
import sys

import click
from dotenv import load_dotenv

from uipath._cli._utils._context import CliContext
from uipath._utils._logs import setup_logging
from uipath._utils.constants import DOTENV_FILE

# Windows console uses codepages (e.g. cp1252) that can't encode Unicode
# characters used by Rich spinners (Braille) and emoji output.
# When piped (not a TTY), keep the system encoding so the parent process
# can decode our output, but use errors="replace" to avoid write-side crashes.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            if _stream.isatty():
                _stream.reconfigure(encoding="utf-8")
            else:
                _stream.reconfigure(errors="replace")
# DO NOT ADD HEAVY IMPORTS HERE
#
# Every import at the top of this file runs on EVERY command.
# Yes, even `--version`. Yes, even `--help`.
#
# We spent hours getting startup from 1.7s → 0.5s.
# If you add `import pandas` here, I will find you.

_LAZY_COMMANDS = {
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
    "server": "cli_server",
    "register": "cli_register",
    "debug": "cli_debug",
    "assets": "services.cli_assets",
    "buckets": "services.cli_buckets",
    "context-grounding": "services.cli_context_grounding",
}

_RUNTIME_COMMANDS = {"init", "dev", "run", "eval", "debug", "server"}

_runtime_initialized = False


def _ensure_runtime_initialized():
    """Initialize runtime factories once, only when needed."""
    global _runtime_initialized
    if _runtime_initialized:
        return
    _runtime_initialized = True

    from uipath._cli.runtimes import load_runtime_factories
    from uipath.functions import register_default_runtime_factory

    register_default_runtime_factory()
    load_runtime_factories()


def _load_command(name: str):
    """Load a CLI command by name."""
    if name not in _LAZY_COMMANDS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    if name in _RUNTIME_COMMANDS:
        _ensure_runtime_initialized()

    module_name = _LAZY_COMMANDS[name]
    mod = __import__(f"uipath._cli.{module_name}", fromlist=[name])
    # CLI names may use hyphens (e.g. "context-grounding") but Python
    # attribute names use underscores; convert before getattr.
    attr_name = name.replace("-", "_")
    return getattr(mod, attr_name)


def __getattr__(name: str):
    """Lazy load CLI commands for mkdocs-click compatibility."""
    return _load_command(name)


def add_cwd_to_path():
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


def load_environment_variables():
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), DOTENV_FILE), override=True)


load_environment_variables()
add_cwd_to_path()


def _get_safe_version() -> str:
    """Get the version of the uipath package."""
    try:
        version = importlib.metadata.version("uipath")
        return version
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _get_format_from_argv() -> str | None:
    for i, arg in enumerate(sys.argv):
        if arg == "--format" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        elif arg.startswith("--format="):
            return arg.split("=", 1)[1]
    return None


class LazyGroup(click.Group):
    """Lazy-load commands only when invoked."""

    def list_commands(self, ctx):
        return sorted(_LAZY_COMMANDS.keys())

    def get_command(self, ctx, cmd_name):
        if cmd_name in _LAZY_COMMANDS:
            return _load_command(cmd_name)
        return None

    def invoke(self, ctx):
        from uipath._cli._utils._console import OutputMode

        try:
            result = super().invoke(ctx)

            # After successful command execution, emit collected output
            cli_ctx = ctx.obj
            if isinstance(cli_ctx, CliContext) and cli_ctx.output_mode is not OutputMode.TEXT:
                from uipath._cli._utils._console import ConsoleLogger

                logger = ConsoleLogger()
                logger.emit()

            return result

        except (SystemExit, click.exceptions.Exit):
            raise

        except click.ClickException as e:
            cli_ctx = getattr(ctx, "obj", None)
            if isinstance(cli_ctx, CliContext) and cli_ctx.output_mode is not OutputMode.TEXT:
                import json as json_mod

                from uipath._cli._utils._console import ConsoleLogger

                logger = ConsoleLogger()
                error_output = {"status": "error", "error": e.format_message()}
                if logger._messages:
                    error_output["messages"] = list(logger._messages)

                click.echo(
                    json_mod.dumps(error_output, indent=2, default=str), err=True
                )
                ctx.exit(1)
            else:
                raise

        except Exception as e:
            cli_ctx = getattr(ctx, "obj", None)
            if isinstance(cli_ctx, CliContext) and cli_ctx.output_mode is not OutputMode.TEXT:
                import json as json_mod

                from uipath._cli._utils._console import CLIError, ConsoleLogger

                logger = ConsoleLogger()

                if isinstance(e, CLIError):
                    messages = e.messages
                    error_msg = e.message
                else:
                    messages = list(logger._messages)
                    error_msg = str(e)

                error_output = {"status": "error", "error": error_msg}
                if messages:
                    error_output["messages"] = messages

                click.echo(
                    json_mod.dumps(error_output, indent=2, default=str), err=True
                )
                ctx.exit(1)
            else:
                raise

    def format_help(self, ctx, formatter):
        format_value = _get_format_from_argv()

        if format_value == "json":
            from uipath._cli._utils._help_json import get_help_json

            json_output = get_help_json(self, ctx, _get_safe_version())
            click.echo(json_output)
            ctx.exit(0)
        else:
            super().format_help(ctx, formatter)


def _parse_output_mode(value: str) -> "OutputMode":
    """Convert click Choice string to OutputMode enum."""
    from uipath._cli._utils._console import OutputMode

    _FORMAT_TO_MODE = {
        "text": OutputMode.TEXT,
        "json": OutputMode.JSON,
        "csv": OutputMode.CSV,
    }
    return _FORMAT_TO_MODE[value]


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
    type=click.Choice(["json", "text", "csv"]),
    default="text",
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
    output_mode = _parse_output_mode(format)
    ctx.obj = CliContext(
        output_mode=output_mode,
        debug=debug,
    )

    setup_logging(should_debug=debug)

    from uipath._cli._utils._console import OutputMode

    if output_mode is not OutputMode.TEXT:
        from uipath._cli._utils._console import ConsoleLogger

        logger = ConsoleLogger()
        logger.output_mode = output_mode

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
