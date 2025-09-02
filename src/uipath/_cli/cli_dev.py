from typing import Optional

import click

from ..telemetry import track
from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()


@click.command()
@click.argument("interface", default="terminal")
@track
def dev(interface: Optional[str]) -> None:
    """Launch interactive debugging interface."""
    console.info("🚀 Starting UiPath Dev Terminal...")
    console.info("Use 'q' to quit, 'n' for new run, 'r' to execute")

    result = Middlewares.next(
        "dev",
        interface,
    )

    if result.should_continue is False:
        return
