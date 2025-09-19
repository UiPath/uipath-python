# type: ignore
import asyncio
import os
from os import environ as env
from typing import Optional

import click

from uipath._cli._utils._debug import setup_debugging
from uipath.tracing import LlmOpsHttpExporter

from .._utils.constants import (
    ENV_JOB_ID,
)
from ..telemetry import track
from ._runtime._contracts import (
    UiPathRuntimeContext,
    UiPathRuntimeError,
    UiPathRuntimeFactory,
)
from ._runtime._runtime import UiPathScriptRuntime
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
@track(when=lambda *_a, **_kw: env.get(ENV_JOB_ID) is None)
def run(
    entrypoint: Optional[str],
    input: Optional[str],
    resume: bool,
    file: Optional[str],
    input_file: Optional[str],
    output_file: Optional[str],
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
        execution_output_file=output_file,
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
            runtime_factory = UiPathRuntimeFactory(
                UiPathScriptRuntime, UiPathRuntimeContext
            )

            context = UiPathRuntimeContext.with_defaults(
                entrypoint=entrypoint,
                input=input,
                input_file=input_file,
                resume=resume,
                execution_output_file=output_file,
                debug=debug,
            )
            if context.job_id:
                runtime_factory.add_span_exporter(LlmOpsHttpExporter())

            asyncio.run(runtime_factory.execute(context))

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
