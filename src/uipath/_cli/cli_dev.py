import asyncio

import click
from uipath.core.tracing import UiPathTraceManager
from uipath.dev import UiPathDeveloperConsole
from uipath.runtime import UiPathRuntimeFactoryRegistry

from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._debug import setup_debugging
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
def dev(interface: str | None, debug: bool, debug_port: int) -> None:
    """Launch interactive debugging interface."""
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

            async def run_terminal() -> None:
                trace_manager = UiPathTraceManager()
                factory = UiPathRuntimeFactoryRegistry.get()

                try:
                    app = UiPathDeveloperConsole(
                        runtime_factory=factory, trace_manager=trace_manager
                    )

                    await app.run_async()

                finally:
                    if factory:
                        await factory.dispose()

            asyncio.run(run_terminal())
        else:
            console.error(f"Unknown interface: {interface}")
    except KeyboardInterrupt:
        console.info("Debug session interrupted by user")
    except Exception as e:
        console.error(
            f"Error running debug interface: {str(e)}", include_traceback=True
        )
