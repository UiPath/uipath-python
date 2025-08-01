# type: ignore
import asyncio
import os
from typing import Optional, Tuple

import click
from dotenv import load_dotenv

from .._utils.constants import ENV_JOB_ID
from ..telemetry import track
from ._evals.evaluation_service import EvaluationService
from ._utils._console import ConsoleLogger

console = ConsoleLogger()
load_dotenv(override=True)


def eval_agent(
    entrypoint: Optional[str] = None,
    eval_set: Optional[str] = None,
    workers: int = 8,
    no_report: bool = False,
    **kwargs,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Core evaluation logic that can be called programmatically.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not provided)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not provided)
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

        service = EvaluationService(
            entrypoint, eval_set, workers, report_progress=not no_report
        )
        asyncio.run(service.run_evaluation())

        return True, None, "Evaluation completed successfully"

    except Exception as e:
        return False, f"Error running evaluation: {str(e)}", None


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("eval_set", required=False)
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
    entrypoint: Optional[str], eval_set: Optional[str], no_report: bool, workers: int
) -> None:
    """Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified)
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
    """
    success, error_message, info_message = eval_agent(
        entrypoint=entrypoint, eval_set=eval_set, workers=workers, no_report=no_report
    )

    if error_message:
        console.error(error_message)
        click.get_current_context().exit(1)

    if info_message:
        console.success(info_message)


if __name__ == "__main__":
    eval()
