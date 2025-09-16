# type: ignore
import ast
import asyncio
import os
from datetime import datetime, timezone
from typing import List, Optional

import click

from uipath._cli._evals._runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath._cli._runtime._contracts import (
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
)
from uipath._cli._runtime._runtime import UiPathScriptRuntime
from uipath._cli.middlewares import MiddlewareResult, Middlewares
from uipath.eval._helpers import auto_discover_entrypoint

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


def eval_agent_middleware(
    entrypoint: Optional[str] = None,
    eval_set: Optional[str] = None,
    eval_ids: Optional[List[str]] = None,
    workers: int = 8,
    no_report: bool = False,
    **kwargs,
) -> MiddlewareResult:
    """Middleware to run an evaluation set against the agent."""
    timestamp = datetime.now(timezone.utc).strftime("%M-%H-%d-%m-%Y")

    eval_context = UiPathEvalContext.with_defaults()
    eval_context.no_report = no_report
    eval_context.workers = workers
    eval_context.eval_set = eval_set or EvalHelpers.auto_discover_eval_set()
    eval_context.eval_ids = eval_ids
    eval_context.execution_output_file = (
        f"evals/results/{timestamp}.json" if not os.getenv("UIPATH_JOB_KEY") else None
    )

    runtime_entrypoint = entrypoint or auto_discover_entrypoint()

    def generate_runtime_context(**context_kwargs) -> UiPathRuntimeContext:
        runtime_context = UiPathRuntimeContext.with_defaults(**context_kwargs)
        runtime_context.entrypoint = runtime_entrypoint
        return runtime_context

    try:
        runtime_factory = UiPathRuntimeFactory(
            UiPathScriptRuntime,
            UiPathRuntimeContext,
            context_generator=generate_runtime_context,
        )

        async def execute():
            async with UiPathEvalRuntime.from_eval_context(
                factory=runtime_factory, context=eval_context
            ) as eval_runtime:
                await eval_runtime.execute()

        asyncio.run(execute())
        return MiddlewareResult(should_continue=False)

    except Exception as e:
        return MiddlewareResult(
            should_continue=False, error_message=f"Error running evaluation: {str(e)}"
        )


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
@track(when=lambda *_a, **_kw: os.getenv(ENV_JOB_ID) is None)
def eval(
    entrypoint: Optional[str],
    eval_set: Optional[str],
    eval_ids: List[str],
    no_report: bool,
    workers: int,
) -> None:
    """Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified)
        eval_ids: Optional list of evaluation IDs
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
    """
    result = Middlewares.next(
        "eval",
        entrypoint,
        eval_set,
        eval_ids,
        no_report=no_report,
        workers=workers,
    )

    if result.should_continue:
        result = eval_agent_middleware(
            entrypoint=entrypoint,
            eval_set=eval_set,
            eval_ids=eval_ids,
            workers=workers,
            no_report=no_report,
        )
    if result.should_continue:
        console.error("Could not process the request with any available handler.")
    if result.error_message:
        console.error(result.error_message)

    console.success("Evaluation completed successfully")


if __name__ == "__main__":
    eval()
