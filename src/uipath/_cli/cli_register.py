# type: ignore
import logging

import click

from ._evals._helpers import register_evaluator
from ._utils._console import ConsoleLogger
from ._utils._resources import Resources

logger = logging.getLogger(__name__)
console = ConsoleLogger()


@click.command()
@click.argument("resource", required=True)
@click.argument("args", nargs=-1)
def register(resource: str, args: tuple[str]) -> None:
    """Register a local resource.

    Examples:
        uipath register evaluator my-custom-evaluator.py
    """
    match Resources.from_string(resource):
        case Resources.EVALUATOR:
            usage_hint = f"Usage: {click.style('uipath register evaluator <evaluator_file_name> (ex. my_custom_evaluator.py)', fg='cyan')}"
            if len(args) < 1:
                console.hint(usage_hint)
                console.error("Missing required argument: evaluator_file_name.")
                return
            if len(args) > 1:
                console.hint(usage_hint)
                console.error(
                    f"Too many arguments provided: {args}. Expected only evaluator_file_name (ex. my_custom_evaluator.py)"
                )

            filename = args[0]

            if not isinstance(filename, str) or not filename.strip():
                console.hint(usage_hint)
                console.error("Invalid filename: must be a non-empty string")
                return

            register_evaluator(filename)
