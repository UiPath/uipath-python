import asyncio
import os
from typing import Optional

import click

from uipath._cli._dev._terminal import UiPathDevTerminal
from uipath._cli._runtime._contracts import UiPathRuntimeContext, UiPathRuntimeFactory
from uipath._cli._runtime._runtime import UiPathScriptRuntime
from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._debug import setup_debugging
from uipath._cli.cli_init import init  # type: ignore[attr-defined]
from uipath._cli.middlewares import Middlewares

console = ConsoleLogger()


@click.command()
@click.argument("interface", default="terminal")
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debugging with debugpy. The process will wait for a debugger to attach.",
)
@click.option(
    "--debug-port",
    type=int,
    default=5678,
    help="Port for the debug server (default: 5678)",
)
def dev(interface: Optional[str], debug: bool, debug_port: int) -> None:
    """Launch interactive debugging interface."""
    project_file = os.path.join(os.getcwd(), "entry-points.json")

    if not os.path.exists(project_file):
        console.warning("Project not initialized. Running `uipath init`...")
        ctx = click.get_current_context()
        ctx.invoke(init)

    if not setup_debugging(debug, debug_port):
        console.error(f"Failed to start debug server on port {debug_port}")

    console.info("Launching UiPath debugging terminal ...")
    result = Middlewares.next(
        "dev",
        interface,
    )

    if result.should_continue is False:
        return

    try:
        if interface == "terminal":
            runtime_factory = UiPathRuntimeFactory(
                UiPathScriptRuntime, UiPathRuntimeContext
            )
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
