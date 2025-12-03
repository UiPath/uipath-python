import asyncio

import click
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeContext, UiPathRuntimeFactoryRegistry

from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._debug import setup_debugging
from uipath._cli.middlewares import Middlewares

console = ConsoleLogger()


def _check_dev_dependency() -> None:
    """Check if uipath-dev is installed and raise helpful error if not."""
    import importlib.util

    if importlib.util.find_spec("uipath.dev") is None:
        raise ImportError(
            "The 'uipath-dev' package is required to use the dev command.\n"
            "Please install it as a development dependency:\n\n"
            "  # Using pip:\n"
            "  pip install uipath-dev\n\n"
            "  # Using uv:\n"
            "  uv add uipath-dev --dev\n\n"
        )


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
    """Launch UiPath Developer Console."""
    try:
        _check_dev_dependency()
    except ImportError as e:
        console.error(str(e))
        return

    if not setup_debugging(debug, debug_port):
        console.error(f"Failed to start debug server on port {debug_port}")

    console.info("Launching UiPath Developer Console ...")
    result = Middlewares.next(
        "dev",
        interface,
    )

    if result.should_continue is False:
        return

    try:
        if interface == "terminal":

            async def run_terminal() -> None:
                from uipath.dev import (  # type: ignore[import-untyped]
                    UiPathDeveloperConsole,
                )

                trace_manager = UiPathTraceManager()
                factory = UiPathRuntimeFactoryRegistry.get(
                    context=UiPathRuntimeContext(
                        trace_manager=trace_manager,
                    )
                )

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
