# type: ignore
import ast
import asyncio
import os
from typing import List, Optional, Tuple

import click

from .._utils.constants import ENV_JOB_ID
from ..telemetry import track
from ._evals.evaluation_service import EvaluationService
from ._utils._console import ConsoleLogger

console = ConsoleLogger()


class LiteralOption(click.Option):
    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except Exception as e:
            raise click.BadParameter(value) from e


def eval_agent(
    entrypoint: Optional[str] = None,
    eval_set: Optional[str] = None,
    eval_ids: Optional[List[str]] = None,
    workers: int = 8,
    no_report: bool = False,
    **kwargs,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Core evaluation logic that can be called programmatically.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not provided)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not provided)
        eval_ids: Optional list of evaluation IDs
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
        **kwargs: Additional arguments for future extensibility

    Returns:
        Tuple containing:
            - success: True if evaluation was successful
            - error_message: Error message if any
            - info_message: Info message if any
    """
    try:
        if workers < 1:
            return False, "Number of workers must be at least 1", None

        print("EVAL SET")
        print(eval_set)
        if eval_set is not None and len(eval_set) == 0:
            return False, "Evaluation set must not be empty", None

        service = EvaluationService(
            entrypoint, eval_set, eval_ids, workers, report_progress=not no_report
        )
        asyncio.run(service.run_evaluation())

        return True, None, "Evaluation completed successfully"

    except Exception as e:
        return False, f"Error running evaluation: {str(e)}", None


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
    success, error_message, info_message = eval_agent(
        entrypoint=entrypoint,
        eval_set=eval_set,
        eval_ids=eval_ids,
        workers=workers,
        no_report=no_report,
    )
    if error_message:
        console.error(error_message)
        click.get_current_context().exit(1)

    if info_message:
        console.success(info_message)


if __name__ == "__main__":
    eval()
