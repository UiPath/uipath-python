# type: ignore
import ast
import asyncio
import os
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

from uipath import UiPath
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
from uipath._cli._utils._constants import UIPATH_PROJECT_ID
from uipath._cli._utils._folders import get_personal_workspace_key_async
from uipath._cli.middlewares import Middlewares
from uipath._events._event_bus import EventBus
from uipath._utils import Endpoint
from uipath._utils.constants import ENV_EVAL_BACKEND_URL, ENV_BASE_URL, ENV_TENANT_ID, HEADER_INTERNAL_TENANT_ID
from uipath.eval._helpers import auto_discover_entrypoint
from uipath.tracing import LlmOpsHttpExporter

from .._utils.constants import ENV_JOB_ID
from ..telemetry import track
from ._utils._console import ConsoleLogger
from ._utils._eval_set import EvalHelpers

console = ConsoleLogger()


async def list_eval_runs() -> None:
    """List previous evaluation runs for the current agent."""
    try:
        project_id = os.getenv(UIPATH_PROJECT_ID)
        if not project_id:
            console.error("UIPATH_PROJECT_ID environment variable not set. Please set it to list previous runs.")
            return

        tenant_id = os.getenv(ENV_TENANT_ID)
        if not tenant_id:
            console.error(f"{ENV_TENANT_ID} env var is not set. Please run 'uipath auth'.")
            return

        # Get eval backend URL
        eval_url = os.getenv(ENV_EVAL_BACKEND_URL)
        if eval_url:
            base_url = eval_url.rstrip("/")
        else:
            base_url = os.getenv(ENV_BASE_URL, "https://cloud.uipath.com").rstrip("/")

        # Initialize UiPath client
        uipath = UiPath()
        client = uipath.api_client

        # Build the endpoint URL
        url = f"{base_url}/api/execution/agents/{project_id}/coded/evalSetRuns"

        # Make the API call
        response = await client.request_async(
            method="GET",
            url=url,
            params={"agentId": project_id},
            headers={HEADER_INTERNAL_TENANT_ID: tenant_id}
        )

        # Parse the response
        import json
        runs = json.loads(response.content)

        if not runs:
            console.info("No previous evaluation runs found for this agent.")
            return

        # Display results in a nice table
        rich_console = Console()
        table = Table(title=f"Evaluation Runs for Agent {project_id}")

        table.add_column("Run ID", style="cyan", no_wrap=True)
        table.add_column("Eval Set ID", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Evals Executed", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Duration (ms)", justify="right")
        table.add_column("Created At", style="yellow")

        for run in runs:
            # Map status: API returns camelCase strings ("pending", "running", "completed")
            status_value = run.get("status", "unknown")
            if isinstance(status_value, str):
                # Handle string status from API
                status_map = {
                    "pending": "Pending",
                    "running": "Running",
                    "completed": "Completed"
                }
                status = status_map.get(status_value.lower(), status_value.capitalize())
            else:
                # Handle integer status as fallback
                status_map = {0: "Pending", 1: "Running", 2: "Completed"}
                status = status_map.get(status_value, "Unknown")

            table.add_row(
                str(run.get("id", "N/A"))[:8] + "...",  # Truncate UUID for display
                run.get("evalSetId", "N/A"),
                status,
                str(run.get("numberOfEvalsExecuted", "N/A")),
                f"{run.get('score', 0):.2f}" if run.get("score") is not None else "N/A",
                str(run.get("durationMilliseconds", "N/A")),
                run.get("createdAt", "N/A")[:19],  # Truncate timestamp
            )

        rich_console.print(table)

        # Show evaluator scores summary
        rich_console.print("\n[bold]Evaluator Scores for Most Recent Run:[/bold]")
        if runs and runs[0].get("evaluatorScores"):
            scores = runs[0]["evaluatorScores"]
            for score in scores:
                evaluator_id = score.get("evaluatorId", "Unknown")
                value = score.get("value", 0)
                rich_console.print(f"  • {evaluator_id}: [green]{value:.2f}[/green]")

    except Exception as e:
        console.error(f"Failed to list eval runs: {e}")


class LiteralOption(click.Option):
    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except Exception as e:
            raise click.BadParameter(value) from e


def setup_reporting_prereq(no_report: bool) -> bool:
    if no_report:
        return False

    if not os.getenv(UIPATH_PROJECT_ID, False):
        console.warning(
            "UIPATH_PROJECT_ID environment variable not set. Results will no be reported to Studio Web."
        )
        return False
    if not os.getenv("UIPATH_FOLDER_KEY"):
        os.environ["UIPATH_FOLDER_KEY"] = asyncio.run(
            get_personal_workspace_key_async()
        )
    return True


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
    "--list-runs",
    is_flag=True,
    help="List previous evaluation runs for this agent",
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
    list_runs: bool,
) -> None:
    """Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified)
        eval_ids: Optional list of evaluation IDs
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
        list_runs: List previous evaluation runs for this agent
    """
    # Suppress HTTP request logs from httpx
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Handle --list-runs flag
    if list_runs:
        asyncio.run(list_eval_runs())
        return

    should_register_progress_reporter = setup_reporting_prereq(no_report)

    result = Middlewares.next(
        "eval",
        entrypoint,
        eval_set,
        eval_ids,
        no_report=no_report,
        workers=workers,
        execution_output_file=output_file,
        register_progress_reporter=should_register_progress_reporter,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        event_bus = EventBus()

        if should_register_progress_reporter:
            progress_reporter = StudioWebProgressReporter(LlmOpsHttpExporter())
            asyncio.run(progress_reporter.subscribe_to_eval_runtime_events(event_bus))

        def generate_runtime_context(**context_kwargs) -> UiPathRuntimeContext:
            runtime_context = UiPathRuntimeContext.with_defaults(**context_kwargs)
            runtime_context.entrypoint = runtime_entrypoint
            return runtime_context

        runtime_entrypoint = entrypoint or auto_discover_entrypoint()

        eval_context = UiPathEvalContext.with_defaults(
            execution_output_file=output_file,
            entrypoint=runtime_entrypoint,
        )

        eval_context.no_report = no_report
        eval_context.workers = workers

        # Load eval set to resolve the path
        eval_set_path = eval_set or EvalHelpers.auto_discover_eval_set()
        _, resolved_eval_set_path = EvalHelpers.load_eval_set(eval_set_path, eval_ids)
        eval_context.eval_set = resolved_eval_set_path
        eval_context.eval_ids = eval_ids

        console_reporter = ConsoleProgressReporter()
        asyncio.run(console_reporter.subscribe_to_eval_runtime_events(event_bus))

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
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )


if __name__ == "__main__":
    eval()
