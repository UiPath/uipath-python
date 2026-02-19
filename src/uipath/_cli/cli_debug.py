import asyncio
import json
import logging
import uuid
from pathlib import Path

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
from uipath.runtime.debug import UiPathDebugProtocol, UiPathDebugRuntime

from uipath._cli._chat._bridge import get_chat_bridge
from uipath._cli._debug._bridge import get_debug_bridge
from uipath._cli._evals._span_collection import ExecutionSpanCollector
from uipath._cli._evals.mocks.mocks import (
    clear_execution_context,
    set_execution_context,
)
from uipath._cli._evals.mocks.types import (
    LLMMockingStrategy,
    MockingContext,
    MockingStrategyType,
    ToolSimulation,
)
from uipath._cli._utils._debug import setup_debugging
from uipath._cli._utils._studio_project import StudioClient
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.platform.common import UiPathConfig
from uipath.tracing import LiveTrackingSpanProcessor, LlmOpsHttpExporter

from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()
logger = logging.getLogger(__name__)


def load_simulation_config() -> MockingContext | None:
    """Load simulation.json from current directory and convert to MockingContext.

    Returns:
        MockingContext with LLM mocking strategy if simulation.json exists and is valid,
        None otherwise.
    """
    simulation_path = Path.cwd() / "simulation.json"

    if not simulation_path.exists():
        return None

    try:
        with open(simulation_path, "r", encoding="utf-8") as f:
            simulation_data = json.load(f)

        # Check if simulation is enabled
        if not simulation_data.get("enabled", True):
            return None

        # Extract tools to simulate
        tools_to_simulate = [
            ToolSimulation(name=tool["name"])
            for tool in simulation_data.get("toolsToSimulate", [])
        ]

        if not tools_to_simulate:
            return None

        # Create LLM mocking strategy
        mocking_strategy = LLMMockingStrategy(
            type=MockingStrategyType.LLM,
            prompt=simulation_data.get("instructions", ""),
            tools_to_simulate=tools_to_simulate,
        )

        # Create MockingContext for debugging
        mocking_context = MockingContext(
            strategy=mocking_strategy,
            name="debug-simulation",
            inputs={},
        )

        console.info(f"Loaded simulation config for {len(tools_to_simulate)} tool(s)")
        return mocking_context

    except Exception as e:
        console.warning(f"Failed to load simulation.json: {e}")
        return None


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

                    # Load simulation config and set up execution context for tool mocking
                    mocking_ctx = load_simulation_config()
                    span_collector: ExecutionSpanCollector | None = None
                    execution_id = str(uuid.uuid4())

                    if mocking_ctx:
                        # Create span collector for trace access during mocking
                        span_collector = ExecutionSpanCollector()
                        # Set execution context to enable tool simulation
                        set_execution_context(mocking_ctx, span_collector, execution_id)

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
                                    delegate=runtime, chat_bridge=chat_bridge
                                )
                                delegate = chat_runtime

                            debug_runtime = UiPathDebugRuntime(
                                delegate=delegate,
                                debug_bridge=debug_bridge,
                                trigger_poll_interval=trigger_poll_interval,
                            )

                            try:
                                ctx.result = await debug_runtime.execute(
                                    ctx.get_input(),
                                    options=UiPathExecuteOptions(resume=resume),
                                )
                            finally:
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
                        # Clear execution context after debugging completes
                        if mocking_ctx:
                            clear_execution_context()

                        if factory:
                            await factory.dispose()

            asyncio.run(execute_debug_runtime())
        except Exception as e:
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )


if __name__ == "__main__":
    debug()
