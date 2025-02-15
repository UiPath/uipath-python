# type: ignore
from typing import Optional

import click

from .middlewares import Middlewares


@click.command()
@click.argument("input", required=False, default="{}")
@click.option("--entrypoint", "-e", help="The entrypoint/graph name")
def run(input: str, entrypoint: Optional[str] = None):
    should_continue, errorMessage = Middlewares.next(
        "run", input, entrypoint=entrypoint
    )

    if errorMessage:
        click.echo(f"{errorMessage}")

    if not should_continue:
        return
