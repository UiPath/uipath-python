# type: ignore
import ast
import asyncio
import logging
import os
import uuid
from typing import List, Optional

import click

from uipath._cli._evals._console_progress_reporter import ConsoleProgressReporter
from uipath._cli._evals._progress_reporter import StudioWebProgressReporter
from uipath._cli._evals._runtime import (
    UiPathEvalContext,
    UiPathEvalRuntime,
)
from uipath._cli._runtime._contracts import (
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
)
from uipath._cli._runtime._runtime import UiPathScriptRuntime
from uipath._cli._utils._folders import get_personal_workspace_key_async
from uipath._cli.middlewares import Middlewares
from uipath._events._event_bus import EventBus
from uipath.eval._helpers import auto_discover_entrypoint
from uipath.tracing import LlmOpsHttpExporter

from .._utils.constants import ENV_JOB_ID
from ..telemetry import track
from ._utils._console import ConsoleLogger
from ._utils._eval_set import EvalHelpers

console = ConsoleLogger()


class LiteralOption(click.Option):
    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except Exception as e:
            raise click.BadParameter(value) from e


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("eval_set", required=False)
@click.option("--eval-ids", cls=LiteralOption, default="[]")
@click.option(
    "--no-report",
    is_flag=True,
    help="Do not report the evaluation results",
    default=False,
)
@click.option(
    "--workers",
    type=int,
    default=8,
    help="Number of parallel workers for running evaluations (default: 8)",
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
    help="Show detailed debug logging output including middleware and HTTP requests",
    default=False,
)
@track(when=lambda *_a, **_kw: os.getenv(ENV_JOB_ID) is None)
def eval(
    entrypoint: Optional[str],
    eval_set: Optional[str],
    eval_ids: List[str],
    no_report: bool,
    workers: int,
    output_file: Optional[str],
    debug: bool,
) -> None:
    """Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified)
        eval_ids: Optional list of evaluation IDs
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
        debug: Show detailed debug logging output
    """
    # Suppress HTTP logs unless in debug mode
    if not debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        os.environ["UIPATH_EVAL_DEBUG"] = "false"
    else:
        os.environ["UIPATH_EVAL_DEBUG"] = "true"

    if not no_report and not os.getenv("UIPATH_FOLDER_KEY"):
        os.environ["UIPATH_FOLDER_KEY"] = asyncio.run(
            get_personal_workspace_key_async()
        )

    result = Middlewares.next(
        "eval",
        entrypoint,
        eval_set,
        eval_ids,
        no_report=no_report,
        workers=workers,
        execution_output_file=output_file,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        event_bus = EventBus()

        # Set up progress reporters
        if not no_report:
            progress_reporter = StudioWebProgressReporter(LlmOpsHttpExporter())
            asyncio.run(progress_reporter.subscribe_to_eval_runtime_events(event_bus))

        # Set up console progress reporter (only when not in debug mode)
        if not debug:
            console_reporter = ConsoleProgressReporter()
            asyncio.run(console_reporter.subscribe_to_eval_runtime_events(event_bus))

        def generate_runtime_context(**context_kwargs) -> UiPathRuntimeContext:
            runtime_context = UiPathRuntimeContext.with_defaults(**context_kwargs)
            runtime_context.entrypoint = runtime_entrypoint
            return runtime_context

        runtime_entrypoint = entrypoint or auto_discover_entrypoint()

        eval_context = UiPathEvalContext.with_defaults(
            execution_output_file=output_file,
            entrypoint=runtime_entrypoint,
            execution_id=str(uuid.uuid4()),
        )

        eval_context.no_report = no_report
        eval_context.workers = workers
        eval_context.eval_set = eval_set or EvalHelpers.auto_discover_eval_set()
        eval_context.eval_ids = eval_ids

        try:
            runtime_factory = UiPathRuntimeFactory(
                UiPathScriptRuntime,
                UiPathRuntimeContext,
                context_generator=generate_runtime_context,
            )
            if eval_context.job_id:
                runtime_factory.add_span_exporter(LlmOpsHttpExporter())

            async def execute():
                async with UiPathEvalRuntime.from_eval_context(
                    factory=runtime_factory,
                    context=eval_context,
                    event_bus=event_bus,
                ) as eval_runtime:
                    await eval_runtime.execute()
                    await event_bus.wait_for_all(timeout=10)

            asyncio.run(execute())
        except Exception as e:
            error_str = str(e)
            if "Evaluation" in error_str and "failed:" in error_str:
                clean_msg = error_str.split("failed:")[-1].strip()
                console.error(f"❌ Evaluation failed: {clean_msg}")
            else:
                console.error(f"❌ Unexpected error occurred: {error_str}")


if __name__ == "__main__":
    eval()