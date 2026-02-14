import asyncio
import signal

import click
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeContext, UiPathRuntimeFactoryRegistry

from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._debug import setup_debugging
from uipath._cli.middlewares import Middlewares

console = ConsoleLogger()


def _check_dev_dependency(interface: str) -> None:
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

    if interface == "web":
        from uipath.dev.server import HAS_EXTRAS  # type: ignore[import-untyped]

        if not HAS_EXTRAS:
            raise ImportError(
                "The 'uipath-dev[server]' package is required to use the web interface.\n"
                "Please install it with the server extras:\n\n"
                "  # Using pip:\n"
                "  pip install uipath-dev[server]\n\n"
                "  # Using uv:\n"
                '  uv add "uipath-dev[server]" --dev\n\n'
            )


@click.command()
@click.argument(
    "interface",
    type=click.Choice(["terminal", "web"], case_sensitive=False),
    default="terminal",
)
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
def dev(interface: str, debug: bool, debug_port: int) -> None:
    """Launch UiPath Developer Console.

    INTERFACE: Choose 'terminal' for console interface (default) or 'web' for browser-based interface.
    """
    try:
        _check_dev_dependency(interface)
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

    if interface == "terminal":

        async def run_terminal() -> None:
            from uipath.dev import (  # type: ignore[import-untyped]
                UiPathDeveloperConsole,
            )

            factory = None
            try:
                trace_manager = UiPathTraceManager()
                factory = UiPathRuntimeFactoryRegistry.get(
                    context=UiPathRuntimeContext(
                        trace_manager=trace_manager, command="dev"
                    )
                )

                app = UiPathDeveloperConsole(
                    runtime_factory=factory, trace_manager=trace_manager
                )

                await app.run_async()

            except KeyboardInterrupt:
                console.info("Debug session interrupted by user")
            finally:
                if factory:
                    try:
                        await factory.dispose()
                    except Exception as e:
                        console.error(f"Error during cleanup: {e}")

        asyncio.run(run_terminal())

    elif interface == "web":

        async def run_web() -> None:
            from uipath.dev.server import (
                UiPathDeveloperServer,
            )

            factory = None
            app = None
            shutdown_event = asyncio.Event()

            def signal_handler(sig, frame):
                """Handle Ctrl+C gracefully."""
                console.info("\nShutting down gracefully...")
                shutdown_event.set()

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            try:
                trace_manager = UiPathTraceManager()
                factory = UiPathRuntimeFactoryRegistry.get(
                    context=UiPathRuntimeContext(
                        trace_manager=trace_manager, command="dev"
                    )
                )

                app = UiPathDeveloperServer(
                    runtime_factory=factory, trace_manager=trace_manager
                )

                server_task = asyncio.create_task(app.run_async())
                shutdown_task = asyncio.create_task(shutdown_event.wait())

                # Wait for either server to complete or shutdown signal
                done, pending = await asyncio.wait(
                    {server_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            except Exception as e:
                console.error(
                    f"Error running debug interface: {str(e)}", include_traceback=True
                )
            finally:
                if factory:
                    try:
                        await factory.dispose()
                    except Exception as e:
                        console.error(f"Error during factory cleanup: {e}")

                await asyncio.sleep(0.2)

        try:
            asyncio.run(run_web())
        except KeyboardInterrupt:
            # Already handled by signal handler
            pass

    else:
        console.error(f"Unknown interface: {interface}")
