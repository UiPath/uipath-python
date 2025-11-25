import asyncio
from typing import Optional

import click
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
)
from uipath.runtime.context import UiPathRuntimeContext
from uipath.runtime.errors import UiPathRuntimeError

from uipath._cli._utils._common import read_resource_overwrites_from_file
from uipath._cli._utils._debug import setup_debugging
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.functions.factory import UiPathFunctionsRuntimeFactory
from uipath.tracing import JsonLinesFileExporter, LlmOpsHttpExporter

from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("input", required=False, default="{}")
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
def run(
    entrypoint: Optional[str],
    input: Optional[str],
    resume: bool,
    file: Optional[str],
    input_file: Optional[str],
    output_file: Optional[str],
    trace_file: Optional[str],
    debug: bool,
    debug_port: int,
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
        debug=debug,
        debug_port=debug_port,
    )

    if result.error_message:
        console.error(result.error_message)
        return

    if result.should_continue:
        if not entrypoint:
            console.error("""No entrypoint specified. Please provide the path to the Python function.
    Usage: `uipath run <entrypoint> <input_arguments> [-f <input_json_file_path>]`""")
            return

        try:

            async def execute_runtime(ctx: UiPathRuntimeContext) -> UiPathRuntimeResult:
                runtime: UiPathRuntimeProtocol | None = None
                with ctx:
                    try:
                        factory = UiPathFunctionsRuntimeFactory(ctx.config_path)
                        runtime = await factory.new_runtime(
                            entrypoint, ctx.job_id or "default"
                        )
                        options = UiPathExecuteOptions(resume=resume)
                        ctx.result = await runtime.execute(
                            input=ctx.get_input(), options=options
                        )
                        return ctx.result
                    finally:
                        if runtime:
                            await runtime.dispose()

            async def execute() -> None:
                ctx = UiPathRuntimeContext.with_defaults(
                    entrypoint=entrypoint,
                    input=input,
                    input_file=file or input_file,
                    output_file=output_file,
                    trace_file=trace_file,
                )

                trace_manager = UiPathTraceManager()

                if ctx.trace_file:
                    trace_manager.add_span_exporter(
                        JsonLinesFileExporter(ctx.trace_file)
                    )

                if ctx.job_id:
                    trace_manager.add_span_exporter(LlmOpsHttpExporter())

                    async with ResourceOverwritesContext(
                        lambda: read_resource_overwrites_from_file(ctx.runtime_dir)
                    ) as rcs_ctx:
                        console.info(
                            f"Applied {rcs_ctx.overwrites_count} resource overwrite(s)"
                        )
                        await execute_runtime(ctx)

                else:
                    result = await execute_runtime(ctx)

                    if result:
                        console.info(f"{result.output}")

            asyncio.run(execute())

        except UiPathRuntimeError as e:
            console.error(f"{e.error_info.title} - {e.error_info.detail}")
        except Exception as e:
            console.error(
                f"Error: Unexpected error occurred - {str(e)}", include_traceback=True
            )

    console.success("Successful execution.")


if __name__ == "__main__":
    run()
