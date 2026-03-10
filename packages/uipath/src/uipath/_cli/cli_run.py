import asyncio

import click

from uipath._cli._chat._bridge import get_chat_bridge
from uipath._cli._debug._bridge import ConsoleDebugBridge
from uipath._cli._utils._common import read_resource_overwrites_from_file
from uipath._cli._utils._debug import setup_debugging
from uipath.core.tracing import UiPathTraceManager
from uipath.platform.common import ResourceOverwritesContext, UiPathConfig
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathStreamOptions,
)
from uipath.runtime.chat import UiPathChatProtocol, UiPathChatRuntime
from uipath.runtime.context import UiPathRuntimeContext
from uipath.runtime.debug import UiPathDebugProtocol
from uipath.runtime.errors import UiPathRuntimeError
from uipath.runtime.events import UiPathRuntimeStateEvent, UiPathRuntimeStatePhase
from uipath.tracing import (
    JsonLinesFileExporter,
    LiveTrackingSpanProcessor,
    LlmOpsHttpExporter,
)

from ._telemetry import track_command
from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()


class _RunDiscoveryError(Exception):
    """Raised when entrypoint auto-discovery fails."""

    def __init__(self, entrypoints: list[str]):
        self.entrypoints = entrypoints


def _show_run_usage_help(entrypoints: list[str]) -> None:
    """Show available entrypoints with usage examples."""
    lines: list[str] = []

    if entrypoints:
        lines.append("Available entrypoints:")
        for name in entrypoints:
            lines.append(f"  - {name}")
    else:
        lines.append(
            "No entrypoints found. "
            "Add a 'functions' or 'agents' section to your config file "
            "(e.g. uipath.json, langgraph.json) "
            "or add MCP slugs to mcp.json."
        )

    lines.append(
        "\nUsage: uipath run <entrypoint> <input_arguments> [-f <input_json_file_path>]"
    )
    if entrypoints:
        lines.append(f"Example: uipath run {entrypoints[0]}")

    click.echo("\n".join(lines))


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
    "--trace-file",
    required=False,
    type=click.Path(exists=False),
    help="File path where the trace spans will be written (JSON Lines format)",
)
@click.option(
    "--state-file",
    required=False,
    type=click.Path(exists=True),
    help="File path where the state file is stored for persisting execution state. If not provided, a temporary file will be used.",
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
@click.option(
    "--keep-state-file",
    is_flag=True,
    help="Keep the temporary state file even when not resuming and no job id is provided",
)
@track_command("run")
def run(
    entrypoint: str | None,
    input: str | None,
    resume: bool,
    file: str | None,
    input_file: str | None,
    output_file: str | None,
    trace_file: str | None,
    state_file: str | None,
    debug: bool,
    debug_port: int,
    keep_state_file: bool,
) -> None:
    """Execute the project."""
    input_file = file or input_file

    # Setup debugging if requested
    if not setup_debugging(debug, debug_port):
        console.error(f"Failed to start debug server on port {debug_port}")

    result = Middlewares.next(
        "run",
        entrypoint,
        input,
        resume,
        input_file=input_file,
        output_file=output_file,
        trace_file=trace_file,
        state_file=state_file,
        debug=debug,
        debug_port=debug_port,
        keep_state_file=keep_state_file,
    )

    if result.error_message:
        console.error(result.error_message)
        return

    if result.should_continue:
        try:

            async def execute_runtime(
                ctx: UiPathRuntimeContext, runtime: UiPathRuntimeProtocol
            ) -> UiPathRuntimeResult:
                options = UiPathExecuteOptions(resume=resume)
                ctx.result = await runtime.execute(
                    input=ctx.get_input(), options=options
                )
                return ctx.result

            async def debug_runtime(
                ctx: UiPathRuntimeContext, runtime: UiPathRuntimeProtocol
            ) -> UiPathRuntimeResult | None:
                debug_bridge: UiPathDebugProtocol = ConsoleDebugBridge()

                await debug_bridge.emit_execution_started()
                options = UiPathStreamOptions(resume=resume)
                async for event in runtime.stream(ctx.get_input(), options=options):
                    if isinstance(event, UiPathRuntimeResult):
                        await debug_bridge.emit_execution_completed(event)
                        ctx.result = event
                    elif isinstance(event, UiPathRuntimeStateEvent):
                        if event.phase == UiPathRuntimeStatePhase.UPDATED:
                            await debug_bridge.emit_state_update(event)
                return ctx.result

            async def execute() -> None:
                trace_manager = UiPathTraceManager()

                ctx = UiPathRuntimeContext.with_defaults(
                    entrypoint=entrypoint,
                    input=input,
                    input_file=file or input_file,
                    output_file=output_file,
                    trace_file=trace_file,
                    state_file_path=state_file,
                    keep_state_file=keep_state_file,
                    resume=resume,
                    command="run",
                    trace_manager=trace_manager,
                )

                if ctx.trace_file:
                    trace_manager.add_span_exporter(
                        JsonLinesFileExporter(ctx.trace_file)
                    )

                async with ResourceOverwritesContext(
                    lambda: read_resource_overwrites_from_file(ctx.runtime_dir)
                ):
                    with ctx:
                        runtime: UiPathRuntimeProtocol | None = None
                        chat_runtime: UiPathRuntimeProtocol | None = None
                        factory: UiPathRuntimeFactoryProtocol | None = None
                        try:
                            factory = UiPathRuntimeFactoryRegistry.get(context=ctx)

                            resolved_entrypoint = entrypoint
                            if not resolved_entrypoint:
                                available = factory.discover_entrypoints()
                                if len(available) == 1:
                                    resolved_entrypoint = available[0]
                                else:
                                    raise _RunDiscoveryError(available)

                            factory_settings = await factory.get_settings()
                            trace_settings = (
                                factory_settings.trace_settings
                                if factory_settings
                                else None
                            )
                            runtime = await factory.new_runtime(
                                resolved_entrypoint,
                                ctx.conversation_id or ctx.job_id or "default",
                            )

                            if ctx.job_id:
                                if UiPathConfig.is_tracing_enabled:
                                    trace_manager.add_span_processor(
                                        LiveTrackingSpanProcessor(
                                            LlmOpsHttpExporter(),
                                            settings=trace_settings,
                                        )
                                    )

                                if ctx.conversation_id and ctx.exchange_id:
                                    chat_bridge: UiPathChatProtocol = get_chat_bridge(
                                        context=ctx
                                    )
                                    chat_runtime = UiPathChatRuntime(
                                        delegate=runtime, chat_bridge=chat_bridge
                                    )

                                ctx.result = await execute_runtime(
                                    ctx, chat_runtime or runtime
                                )
                            else:
                                ctx.result = await debug_runtime(ctx, runtime)
                        finally:
                            if chat_runtime:
                                await chat_runtime.dispose()
                            if runtime:
                                await runtime.dispose()
                            if factory:
                                await factory.dispose()

            asyncio.run(execute())

        except _RunDiscoveryError as e:
            _show_run_usage_help(e.entrypoints)
            return
        except UiPathRuntimeError as e:
            console.error(f"{e.error_info.title} - {e.error_info.detail}")
            return
        except Exception as e:
            console.error(
                f"Error: Unexpected error occurred - {str(e)}", include_traceback=True
            )
            return

    console.success("Successful execution.")


if __name__ == "__main__":
    run()
