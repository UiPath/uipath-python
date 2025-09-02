import asyncio
from typing import Optional

import click

from ..telemetry import track
from ._dev._terminal import UiPathDevTerminal
from ._runtime._contracts import UiPathRuntimeContext, UiPathRuntimeFactory
from ._runtime._runtime import UiPathRuntime
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

    try:
        if interface == "terminal":
            runtime_factory = UiPathRuntimeFactory(UiPathRuntime, UiPathRuntimeContext)
            app = UiPathDevTerminal(runtime_factory)
            asyncio.run(app.run_async())
        else:
            console.error(f"Unknown interface: {interface}")
    except KeyboardInterrupt:
        console.info("Debug session interrupted by user")
    except Exception as e:
        console.error(
            f"Error running debug interface: {str(e)}", include_traceback=True
        )
