"""Helper functions for evaluation process."""

import functools
import time
from collections.abc import Callable
from typing import Any

from ..models import ErrorEvaluationResult, EvaluationResult


def is_empty_value(value: Any) -> bool:
    """Check if a value is empty or contains only empty values.

    Handles multiple cases:
    - None or empty string
    - String with only whitespace
    - Dict where all values are empty strings or whitespace
    - Empty list or dict
    """
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, dict):
        if not value:  # Empty dict
            return True
        # Check if all values are empty strings
        return all(isinstance(v, str) and not v.strip() for v in value.values())

    if isinstance(value, list):
        return len(value) == 0

    return False


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
