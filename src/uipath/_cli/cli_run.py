# type: ignore
import asyncio
import os
from typing import Optional

import click

from uipath._cli._runtime._runtime_factory import generate_runtime_factory
from uipath._cli._utils._common import read_resource_overwrites_from_file
from uipath._cli._utils._debug import setup_debugging
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.tracing import JsonLinesFileExporter, LlmOpsHttpExporter

from ._runtime._contracts import UiPathRuntimeError
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
    context_args = {
        "entrypoint": entrypoint,
        "input": input,
        "resume": resume,
        "input_file": file or input_file,
        "execution_output_file": output_file,
        "trace_file": trace_file,
        "debug": debug,
    }
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
        execution_output_file=output_file,
        trace_file=trace_file,
        debug=debug,
        debug_port=debug_port,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        if not entrypoint:
            console.error("""No entrypoint specified. Please provide a path to a Python script.
    Usage: `uipath run <entrypoint_path> <input_arguments> [-f <input_json_file_path>]`""")

        if not os.path.exists(entrypoint):
            console.error(f"""Script not found at path {entrypoint}.
    Usage: `uipath run <entrypoint_path> <input_arguments> [-f <input_json_file_path>]`""")

        try:

            async def execute() -> None:
                runtime_factory = generate_runtime_factory()
                context = runtime_factory.new_context(**context_args)
                if context.job_id:
                    runtime_factory.add_span_exporter(LlmOpsHttpExporter())

                if trace_file:
                    runtime_factory.add_span_exporter(JsonLinesFileExporter(trace_file))

                if context.job_id:
                    async with ResourceOverwritesContext(
                        lambda: read_resource_overwrites_from_file(context.runtime_dir)
                    ) as ctx:
                        console.info(
                            f"Applied {ctx.overwrites_count} resource overwrite(s)"
                        )

                        result = await runtime_factory.execute(context)
                else:
                    result = await runtime_factory.execute(context)

                if not context.job_id:
                    console.info(result.output)

            asyncio.run(execute())

        except UiPathRuntimeError as e:
            console.error(f"{e.error_info.title} - {e.error_info.detail}")
        except Exception as e:
            # Handle unexpected errors
            console.error(
                f"Error: Unexpected error occurred - {str(e)}", include_traceback=True
            )

    console.success("Successful execution.")


if __name__ == "__main__":
    run()
