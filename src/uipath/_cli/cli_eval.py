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
@click.argument("eval_set", required=True, type=click.Path(exists=True))
@track(when=lambda *_a, **_kw: os.getenv(ENV_JOB_ID) is None)
def eval(eval_set: str) -> None:
    """Run an evaluation set against the agent.

    Args:
        eval_set: Path to the evaluation set JSON file
    """
    try:
        # Validate file path
        eval_path = Path(eval_set)
        if not eval_path.is_file() or eval_path.suffix != ".json":
            console.error("Evaluation set must be a JSON file")
            click.get_current_context().exit(1)

        # Run evaluation
        service = EvaluationService(eval_set)
        asyncio.run(service.run_evaluation())

    except Exception as e:
        console.error(f"Error running evaluation: {str(e)}")
        click.get_current_context().exit(1)


if __name__ == "__main__":
    eval()
