# type: ignore
import asyncio
import os
from pathlib import Path
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
    entrypoint: str, eval_set: str, workers: int = 8, **kwargs
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Core evaluation logic that can be called programmatically.

    Args:
        entrypoint: Path to the agent script to evaluate
        eval_set: Path to the evaluation set JSON file
        workers: Number of parallel workers for running evaluations
        **kwargs: Additional arguments for future extensibility

    Returns:
        Tuple containing:
            - success: True if evaluation was successful
            - error_message: Error message if any
            - info_message: Info message if any
    """
    try:
        # Validate file path
        eval_path = Path(eval_set)
        if not eval_path.is_file() or eval_path.suffix != ".json":
            return False, "Evaluation set must be a JSON file", None

        # Validate workers count
        if workers < 1:
            return False, "Number of workers must be at least 1", None

        # Run evaluation
        service = EvaluationService(entrypoint, eval_set, workers)
        asyncio.run(service.run_evaluation())

        return True, None, "Evaluation completed successfully"

    except Exception as e:
        return False, f"Error running evaluation: {str(e)}", None


@click.command()
@click.argument("entrypoint", required=True)
@click.argument("eval_set", required=True, type=click.Path(exists=True))
@click.option(
    "--workers",
    type=int,
    default=8,
    help="Number of parallel workers for running evaluations (default: 8)",
)
@track(when=lambda *_a, **_kw: os.getenv(ENV_JOB_ID) is None)
def eval(entrypoint: str, eval_set: str, workers: int) -> None:
    """Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate
        eval_set: Path to the evaluation set JSON file
        workers: Number of parallel workers for running evaluations
    """
    success, error_message, info_message = eval_agent(
        entrypoint=entrypoint, eval_set=eval_set, workers=workers
    )

    if error_message:
        console.error(error_message)
        click.get_current_context().exit(1)

    if info_message:
        console.success(info_message)


if __name__ == "__main__":
    eval()
