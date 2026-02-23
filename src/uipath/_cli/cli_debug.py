import asyncio
import logging

import click

from uipath._cli._chat._bridge import get_chat_bridge
from uipath._cli._debug._bridge import get_debug_bridge
from uipath._cli._utils._debug import setup_debugging
from uipath._cli._utils._studio_project import StudioClient
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.mocks import UiPathMockRuntime
from uipath.platform.common import ResourceOverwritesContext, UiPathConfig
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeContext,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeProtocol,
)
from uipath.runtime.chat import UiPathChatProtocol, UiPathChatRuntime
from uipath.runtime.debug import UiPathDebugProtocol, UiPathDebugRuntime
from uipath.tracing import LiveTrackingSpanProcessor, LlmOpsHttpExporter

from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()
logger = logging.getLogger(__name__)


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
                    factory: UiPathRuntimeFactoryProtocol | None = None

                    try:
                        trigger_poll_interval: float = 5.0

                        factory = UiPathRuntimeFactoryRegistry.get(context=ctx)
                        factory_settings = await factory.get_settings()
                        trace_settings = (
                            factory_settings.trace_settings
                            if factory_settings
                            else None
                        )

                        if ctx.job_id:
                            if UiPathConfig.is_tracing_enabled:
                                trace_manager.add_span_processor(
                                    LiveTrackingSpanProcessor(
                                        LlmOpsHttpExporter(),
                                        settings=trace_settings,
                                    )
                                )
                            trigger_poll_interval = (
                                0.0  # Polling disabled for production jobs
                            )

                        async def execute_debug_runtime():
                            chat_runtime: UiPathRuntimeProtocol | None = None
                            debug_bridge: UiPathDebugProtocol = get_debug_bridge(ctx)

                            runtime = await factory.new_runtime(
                                entrypoint,
                                ctx.conversation_id or ctx.job_id or "default",
                            )

                            delegate = runtime
                            if ctx.conversation_id and ctx.exchange_id:
                                chat_bridge: UiPathChatProtocol = get_chat_bridge(
                                    context=ctx
                                )
                                chat_runtime = UiPathChatRuntime(
                                    delegate=delegate, chat_bridge=chat_bridge
                                )
                                delegate = chat_runtime

                            debug_runtime = UiPathDebugRuntime(
                                delegate=delegate,
                                debug_bridge=debug_bridge,
                                trigger_poll_interval=trigger_poll_interval,
                            )

                            mock_runtime = UiPathMockRuntime(
                                delegate=debug_runtime,
                            )

                            try:
                                ctx.result = await mock_runtime.execute(
                                    ctx.get_input(),
                                    options=UiPathExecuteOptions(resume=resume),
                                )
                            finally:
                                await mock_runtime.dispose()
                                await debug_runtime.dispose()
                                if chat_runtime:
                                    await chat_runtime.dispose()
                                await runtime.dispose()

                        if project_id := UiPathConfig.project_id:
                            studio_client = StudioClient(project_id)

                            async with ResourceOverwritesContext(
                                lambda: studio_client.get_resource_overwrites()
                            ):
                                await execute_debug_runtime()
                        else:
                            logger.debug(
                                "No UIPATH_PROJECT_ID configured, executing without resource overwrites"
                            )
                            await execute_debug_runtime()

                    finally:
                        if factory:
                            await factory.dispose()

            asyncio.run(execute_debug_runtime())
        except Exception as e:
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )


if __name__ == "__main__":
    debug()
