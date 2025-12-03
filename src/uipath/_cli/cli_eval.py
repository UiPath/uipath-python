import ast
import asyncio
import os

import click
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeContext, UiPathRuntimeFactoryRegistry

from uipath._cli._evals._console_progress_reporter import ConsoleProgressReporter
from uipath._cli._evals._evaluate import evaluate
from uipath._cli._evals._progress_reporter import StudioWebProgressReporter
from uipath._cli._evals._runtime import (
    UiPathEvalContext,
)
from uipath._cli._utils._folders import get_personal_workspace_key_async
from uipath._cli._utils._studio_project import StudioClient
from uipath._cli.middlewares import Middlewares
from uipath._events._event_bus import EventBus
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.eval._helpers import auto_discover_entrypoint
from uipath.platform.common import UiPathConfig
from uipath.tracing import LlmOpsHttpExporter

from ._utils._console import ConsoleLogger
from ._utils._eval_set import EvalHelpers

console = ConsoleLogger()


class LiteralOption(click.Option):
    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except Exception as e:
            raise click.BadParameter(value) from e


def setup_reporting_prereq(no_report: bool) -> bool:
    if no_report:
        return False

    if not UiPathConfig.is_studio_project:
        console.warning(
            "UIPATH_PROJECT_ID environment variable not set. Results will no be reported to Studio Web."
        )
        return False

    if not UiPathConfig.folder_key:
        folder_key = asyncio.run(get_personal_workspace_key_async())
        if folder_key:
            os.environ["UIPATH_FOLDER_KEY"] = folder_key
    return True


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("eval_set", required=False)
@click.option("--eval-ids", cls=LiteralOption, default="[]")
@click.option(
    "--eval-set-run-id",
    required=False,
    type=str,
    help="Custom evaluation set run ID (if not provided, a UUID will be generated)",
)
@click.option(
    "--no-report",
    is_flag=True,
    help="Do not report the evaluation results",
    default=False,
)
@click.option(
    "--workers",
    type=int,
    default=1,
    help="Number of parallel workers for running evaluations (default: 1)",
)
@click.option(
    "--output-file",
    required=False,
    type=click.Path(exists=False),
    help="File path where the output will be written",
)
@click.option(
    "--enable-mocker-cache",
    is_flag=True,
    default=False,
    help="Enable caching for LLM mocker responses",
)
@click.option(
    "--report-coverage",
    is_flag=True,
    default=False,
    help="Report evaluation coverage",
)
def eval(
    entrypoint: str | None,
    eval_set: str | None,
    eval_ids: list[str],
    eval_set_run_id: str | None,
    no_report: bool,
    workers: int,
    output_file: str | None,
    enable_mocker_cache: bool,
    report_coverage: bool,
) -> None:
    """Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified)
        eval_ids: Optional list of evaluation IDs
        eval_set_run_id: Custom evaluation set run ID (optional, will generate UUID if not specified)
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
        enable_mocker_cache: Enable caching for LLM mocker responses
        report_coverage: Report evaluation coverage
    """
    should_register_progress_reporter = setup_reporting_prereq(no_report)

    result = Middlewares.next(
        "eval",
        entrypoint,
        eval_set,
        eval_ids,
        eval_set_run_id=eval_set_run_id,
        no_report=no_report,
        workers=workers,
        output_file=output_file,
        register_progress_reporter=should_register_progress_reporter,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        eval_context = UiPathEvalContext()

        eval_context.entrypoint = entrypoint or auto_discover_entrypoint()
        eval_context.no_report = no_report
        eval_context.workers = workers
        eval_context.eval_set_run_id = eval_set_run_id
        eval_context.enable_mocker_cache = enable_mocker_cache

        # Load eval set to resolve the path
        eval_set_path = eval_set or EvalHelpers.auto_discover_eval_set()
        _, resolved_eval_set_path = EvalHelpers.load_eval_set(eval_set_path, eval_ids)

        eval_context.eval_set = resolved_eval_set_path
        eval_context.eval_ids = eval_ids
        eval_context.report_coverage = report_coverage

        try:

            async def execute_eval():
                event_bus = EventBus()

                if should_register_progress_reporter:
                    progress_reporter = StudioWebProgressReporter(LlmOpsHttpExporter())
                    await progress_reporter.subscribe_to_eval_runtime_events(event_bus)

                console_reporter = ConsoleProgressReporter()
                await console_reporter.subscribe_to_eval_runtime_events(event_bus)

                trace_manager = UiPathTraceManager()

                with UiPathRuntimeContext.with_defaults(
                    output_file=output_file,
                    trace_manager=trace_manager,
                    command="eval",
                ) as ctx:
                    if ctx.job_id:
                        trace_manager.add_span_exporter(LlmOpsHttpExporter())

                    project_id = UiPathConfig.project_id

                    runtime_factory = UiPathRuntimeFactoryRegistry.get(context=ctx)

                    try:
                        if project_id:
                            studio_client = StudioClient(project_id)

                            async with ResourceOverwritesContext(
                                lambda: studio_client.get_resource_overwrites()
                            ):
                                ctx.result = await evaluate(
                                    runtime_factory,
                                    trace_manager,
                                    eval_context,
                                    event_bus,
                                )
                        else:
                            # Fall back to execution without overwrites
                            ctx.result = await evaluate(
                                runtime_factory, trace_manager, eval_context, event_bus
                            )
                    finally:
                        if runtime_factory:
                            await runtime_factory.dispose()

            asyncio.run(execute_eval())

        except Exception as e:
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )


if __name__ == "__main__":
    eval()
