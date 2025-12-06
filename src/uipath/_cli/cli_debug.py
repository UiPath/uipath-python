import asyncio

import click
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeContext,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeProtocol,
)
from uipath.runtime.chat import UiPathChatProtocol, UiPathChatRuntime
from uipath.runtime.debug import UiPathDebugBridgeProtocol, UiPathDebugRuntime

from uipath._cli._chat._bridge import get_chat_bridge
from uipath._cli._debug._bridge import get_debug_bridge
from uipath._cli._utils._debug import setup_debugging
from uipath._cli._utils._studio_project import StudioClient
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.platform.common import UiPathConfig
from uipath.tracing import LlmOpsHttpExporter

from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("input", required=False, default=None)
@click.option("--resume", is_flag=True, help="Resume execution from a previous state")
@click.option(
    "-f",
    "--file",
    required=False,
    type=click.Path(exists=True),
    help="File path for the .json input",
)
@click.option(
    "--input-file",
    required=False,
    type=click.Path(exists=True),
    help="Alias for '-f/--file' arguments",
)
@click.option(
    "--output-file",
    required=False,
    type=click.Path(exists=False),
    help="File path where the output will be written",
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
def debug(
    entrypoint: str | None,
    input: str | None,
    resume: bool,
    file: str | None,
    input_file: str | None,
    output_file: str | None,
    debug: bool,
    debug_port: int,
) -> None:
    """Debug the project."""
    input_file = file or input_file
    # Setup debugging if requested
    if not setup_debugging(debug, debug_port):
        console.error(f"Failed to start debug server on port {debug_port}")

    result = Middlewares.next(
        "debug",
        entrypoint,
        input,
        resume,
        input_file=input_file,
        output_file=output_file,
        debug=debug,
        debug_port=debug_port,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        if not entrypoint:
            console.error("""No entrypoint specified.
    Usage: `uipath debug <entrypoint> <input_arguments> [-f <input_json_file_path>]`""")
            return

        try:

            async def execute_debug_runtime():
                trace_manager = UiPathTraceManager()

                with UiPathRuntimeContext.with_defaults(
                    input=input,
                    input_file=input_file,
                    output_file=output_file,
                    resume=resume,
                    trace_manager=trace_manager,
                    command="debug",
                ) as ctx:
                    runtime: UiPathRuntimeProtocol | None = None
                    chat_runtime: UiPathRuntimeProtocol | None = None
                    debug_runtime: UiPathRuntimeProtocol | None = None
                    factory: UiPathRuntimeFactoryProtocol | None = None

                    try:
                        trigger_poll_interval: float = 5.0

                        factory = UiPathRuntimeFactoryRegistry.get(context=ctx)

                        runtime = await factory.new_runtime(
                            entrypoint, ctx.conversation_id or ctx.job_id or "default"
                        )

                        if ctx.job_id:
                            trace_manager.add_span_exporter(LlmOpsHttpExporter())
                            trigger_poll_interval = (
                                0.0  # Polling disabled for production jobs
                            )
                            if ctx.conversation_id and ctx.exchange_id:
                                chat_bridge: UiPathChatProtocol = get_chat_bridge(
                                    context=ctx
                                )
                                chat_runtime = UiPathChatRuntime(
                                    delegate=runtime, chat_bridge=chat_bridge
                                )

                        debug_bridge: UiPathDebugBridgeProtocol = get_debug_bridge(ctx)

                        debug_runtime = UiPathDebugRuntime(
                            delegate=chat_runtime or runtime,
                            debug_bridge=debug_bridge,
                            trigger_poll_interval=trigger_poll_interval,
                        )

                        project_id = UiPathConfig.project_id

                        if project_id:
                            studio_client = StudioClient(project_id)

                            async with ResourceOverwritesContext(
                                lambda: studio_client.get_resource_overwrites()
                            ):
                                ctx.result = await debug_runtime.execute(
                                    ctx.get_input(),
                                    options=UiPathExecuteOptions(resume=resume),
                                )
                        else:
                            ctx.result = await debug_runtime.execute(
                                ctx.get_input(),
                                options=UiPathExecuteOptions(resume=resume),
                            )

                    finally:
                        if debug_runtime:
                            await debug_runtime.dispose()
                        if chat_runtime:
                            await chat_runtime.dispose()
                        if runtime:
                            await runtime.dispose()
                        if factory:
                            await factory.dispose()

            asyncio.run(execute_debug_runtime())
        except Exception as e:
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )


if __name__ == "__main__":
    debug()
