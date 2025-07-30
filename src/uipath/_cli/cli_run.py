# type: ignore
import asyncio
import os
import traceback
from os import environ as env
from typing import Optional, Tuple
from uuid import uuid4

import click
from dotenv import load_dotenv

from uipath._cli._utils._debug import setup_debugging

from .._utils.constants import (
    ENV_JOB_ID,
)
from ..telemetry import track
from ._runtime._contracts import (
    UiPathRuntimeContext,
    UiPathRuntimeError,
    UiPathTraceContext,
)
from ._runtime._runtime import UiPathRuntime
from ._utils._console import ConsoleLogger
from .middlewares import MiddlewareResult, Middlewares

console = ConsoleLogger()
load_dotenv(override=True)


def python_run_middleware(
    entrypoint: Optional[str],
    input: Optional[str],
    resume: bool,
    **kwargs,
) -> MiddlewareResult:
    """Middleware to handle Python script execution.

    Args:
        entrypoint: Path to the Python script to execute
        input: JSON string with input data
        resume: Flag indicating if this is a resume execution
        debug: Enable debugging with debugpy
        debug_port: Port for debug server (default: 5678)

    Returns:
        MiddlewareResult with execution status and messages
    """
    if not entrypoint:
        return MiddlewareResult(
            should_continue=False,
            error_message="""No entrypoint specified. Please provide a path to a Python script.
Usage: `uipath run <entrypoint_path> <input_arguments> [-f <input_json_file_path>]`""",
        )

    if not os.path.exists(entrypoint):
        return MiddlewareResult(
            should_continue=False,
            error_message=f"""Script not found at path {entrypoint}.
Usage: `uipath run <entrypoint_path> <input_arguments> [-f <input_json_file_path>]`""",
        )

    try:

        async def execute():
            context = UiPathRuntimeContext.from_config(
                env.get("UIPATH_CONFIG_PATH", "uipath.json"), **kwargs
            )
            context.entrypoint = entrypoint
            context.input = input
            context.resume = resume
            context.job_id = env.get("UIPATH_JOB_KEY")
            context.trace_id = env.get("UIPATH_TRACE_ID")
            context.input_file = kwargs.get("input_file", None)
            context.execution_output_file = kwargs.get("execution_output_file", None)
            context.is_eval_run = kwargs.get("is_eval_run", False)
            context.tracing_enabled = env.get("UIPATH_TRACING_ENABLED", True)
            context.trace_context = UiPathTraceContext(
                trace_id=env.get("UIPATH_TRACE_ID"),
                parent_span_id=env.get("UIPATH_PARENT_SPAN_ID"),
                root_span_id=env.get("UIPATH_ROOT_SPAN_ID"),
                enabled=env.get("UIPATH_TRACING_ENABLED", True),
                job_id=env.get("UIPATH_JOB_KEY"),
                org_id=env.get("UIPATH_ORGANIZATION_ID"),
                tenant_id=env.get("UIPATH_TENANT_ID"),
                process_key=env.get("UIPATH_PROCESS_UUID"),
                folder_key=env.get("UIPATH_FOLDER_KEY"),
                reference_id=env.get("UIPATH_JOB_KEY") or str(uuid4()),
            )
            context.logs_min_level = env.get("LOG_LEVEL", "INFO")
            async with UiPathRuntime.from_context(context) as runtime:
                await runtime.execute()

        asyncio.run(execute())

        # Return success
        return MiddlewareResult(should_continue=False)

    except UiPathRuntimeError as e:
        return MiddlewareResult(
            should_continue=False,
            error_message=f"Error: {e.error_info.title} - {e.error_info.detail}",
            should_include_stacktrace=False,
        )
    except Exception as e:
        # Handle unexpected errors
        return MiddlewareResult(
            should_continue=False,
            error_message=f"Error: Unexpected error occurred - {str(e)}",
            should_include_stacktrace=True,
        )


def run_core(
    entrypoint: Optional[str],
    resume: bool,
    input: Optional[str] = None,
    input_file: Optional[str] = None,
    execution_output_file: Optional[str] = None,
    logs_file: Optional[str] = None,
    **kwargs,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Core execution logic that can be called programmatically.

    Args:
        entrypoint: Path to the Python script to execute
        input: JSON string with input data
        resume: Flag indicating if this is a resume execution
        input_file: Path to input JSON file
        execution_output_file: Path to execution output file
        logs_file: Path where execution output will be written
        **kwargs: Additional arguments to be forwarded to the middleware

    Returns:
        Tuple containing:
            - success: True if execution was successful
            - error_message: Error message if any
            - info_message: Info message if any
    """
    # Process through middleware chain
    result = Middlewares.next(
        "run",
        entrypoint,
        input,
        resume,
        input_file=input_file,
        execution_output_file=execution_output_file,
        logs_file=logs_file,
        **kwargs,
    )

    if result.should_continue:
        result = python_run_middleware(
            entrypoint=entrypoint,
            input=input,
            resume=resume,
            input_file=input_file,
            execution_output_file=execution_output_file,
            logs_file=logs_file,
            **kwargs,
        )

    if result.should_continue:
        return False, "Could not process the request with any available handler.", None

    return (
        not bool(result.error_message),
        result.error_message,
        result.info_message,
    )


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

    success, error_message, info_message = run_core(
        entrypoint=entrypoint,
        input=input,
        resume=resume,
        input_file=input_file,
        execution_output_file=output_file,
        debug=debug,
        debug_port=debug_port,
    )

    if error_message:
        console.error(error_message, include_traceback=True)
        if not success:  # If there was an error and execution failed
            console.error(traceback.format_exc())
        click.get_current_context().exit(1)

    if info_message:
        console.info(info_message)

    if success:
        console.success("Successful execution.")


if __name__ == "__main__":
    run()
