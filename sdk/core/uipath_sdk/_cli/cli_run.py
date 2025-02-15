# type: ignore
from typing import Any

import click
from middlewares import Middlewares


@click.command()
def run(*args: Any, **kwargs: Any):
    should_continue, errorMessage = Middlewares.next("run", *args, **kwargs)

    if errorMessage:
        click.echo(f"{errorMessage}")

    if not should_continue:
        return
