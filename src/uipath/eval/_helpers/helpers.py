import functools
import json
import os
import time
from collections.abc import Callable
from typing import Any

import click

from ..models import ErrorEvaluationResult, EvaluationResult


def auto_discover_entrypoint() -> str:
    """Auto-discover entrypoint from config file.

    Returns:
        Entrypoint name (key from the functions dict)

    Raises:
        ValueError: If no entrypoint found or multiple entrypoints exist
    """
    from uipath._cli._utils._console import ConsoleLogger
    from uipath._utils.constants import UIPATH_CONFIG_FILE

    console = ConsoleLogger()

    if not os.path.isfile(UIPATH_CONFIG_FILE):
        raise ValueError(
            f"File '{UIPATH_CONFIG_FILE}' not found. Please run 'uipath init'."
        )

    with open(UIPATH_CONFIG_FILE, "r", encoding="utf-8") as f:
        uipath_config = json.loads(f.read())

    entrypoints: dict[str, str] = uipath_config.get("functions", {})

    if not entrypoints:
        raise ValueError(
            f"No entrypoints found in {UIPATH_CONFIG_FILE}. "
            "Add a 'functions' section to uipath.json"
        )

    if len(entrypoints) > 1:
        entrypoint_list = list(entrypoints.keys())
        raise ValueError(
            f"Multiple entrypoints found: {entrypoint_list}. "
            "Please specify which entrypoint to use."
        )

    entrypoint_name = next(iter(entrypoints.keys()))
    entrypoint_path = entrypoints[entrypoint_name]
    console.info(
        f"Auto-discovered entrypoint: {click.style(entrypoint_name, fg='cyan')} "
        f"({entrypoint_path})"
    )
    return entrypoint_name


def track_evaluation_metrics(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to track evaluation metrics and handle errors gracefully."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> EvaluationResult:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
        except Exception as e:
            result = ErrorEvaluationResult(
                details="Exception thrown by evaluator: {}".format(e),
                evaluation_time=time.time() - start_time,
            )
        end_time = time.time()
        execution_time = end_time - start_time

        result.evaluation_time = execution_time
        return result

    return wrapper
