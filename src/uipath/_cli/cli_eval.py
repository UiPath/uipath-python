# type: ignore
import asyncio
import os
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from .._utils.constants import ENV_JOB_ID
from ..telemetry import track
from ._evals.evaluation_service import EvaluationService
from ._utils._console import ConsoleLogger

console = ConsoleLogger()
load_dotenv(override=True)


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
    try:
        # Validate file path
        eval_path = Path(eval_set)
        if not eval_path.is_file() or eval_path.suffix != ".json":
            console.error("Evaluation set must be a JSON file")
            click.get_current_context().exit(1)

        # Validate workers count
        if workers < 1:
            console.error("Number of workers must be at least 1")
            click.get_current_context().exit(1)

        # Run evaluation
        service = EvaluationService(entrypoint, eval_set, workers)
        asyncio.run(service.run_evaluation())

    except Exception as e:
        console.error(f"Error running evaluation: {str(e)}")
        click.get_current_context().exit(1)


if __name__ == "__main__":
    eval()
