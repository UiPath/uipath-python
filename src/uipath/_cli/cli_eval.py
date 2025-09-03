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
    UiPathRuntimeContextBuilder,
    UiPathRuntimeFactory,
)
from uipath._cli._runtime._runtime import UiPathRuntime
from uipath._cli.middlewares import MiddlewareResult, Middlewares

from .._utils.constants import ENV_JOB_ID
from ..telemetry import track
from ._utils._console import ConsoleLogger

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
    def generate_eval_context(
        runtime_context: UiPathRuntimeContext,
    ) -> UiPathEvalContext:
        os.makedirs("evals/results", exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%M-%H-%d-%m-%Y")
        base_context = UiPathRuntimeContextBuilder().with_defaults().build()
        # TODO: the name should include the eval_set name. those files should not be commited to SW
        base_context.execution_output_file = (
            f"evals/results/{timestamp}.json"
            if not os.getenv("UIPATH_JOB_KEY")
            else None
        )
        return UiPathEvalContext(
            runtime_context=runtime_context,
            no_report=no_report,
            workers=workers,
            eval_set=eval_set,
            eval_ids=eval_ids,
            **kwargs,
            **base_context.model_dump(),
        )

    try:
        runtime_factory = UiPathRuntimeFactory(UiPathRuntime, UiPathRuntimeContext)
        context = (
            UiPathRuntimeContextBuilder()
            .with_defaults(**kwargs)
            .with_entrypoint(entrypoint)
            .with_entrypoint(entrypoint)
            .mark_eval_run()
            .build()
        )

        async def execute():
            async with UiPathEvalRuntime.from__eval_context(
                factory=runtime_factory, context=generate_eval_context(context)
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
