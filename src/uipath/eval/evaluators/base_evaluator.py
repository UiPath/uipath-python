"""Base evaluator abstract class for agent evaluation."""

import functools
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from uipath.eval.models import EvaluationResult
from uipath.eval.models.models import (
    AgentExecution,
    ErrorEvaluationResult,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


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


T = TypeVar("T")


class LegacyBaseEvaluator(BaseModel, Generic[T], ABC):
    """Abstract base class for all evaluators."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    name: str
    description: str
    target_output_key: str = "*"
    created_at: str
    updated_at: str
    category: LegacyEvaluatorCategory
    evaluator_type: LegacyEvaluatorType

    def __init_subclass__(cls, **kwargs: Any):
        """Hook for subclass creation - automatically applies evaluation metrics tracking."""
        super().__init_subclass__(**kwargs)

        if hasattr(cls, "evaluate") and not getattr(
            cls.evaluate, "_has_metrics_decorator", False
        ):
            cls.evaluate = track_evaluation_metrics(cls.evaluate)  # type: ignore[method-assign]
            cls.evaluate._has_metrics_decorator = True  # type: ignore[attr-defined]

    def model_post_init(self, __context: Any):
        """Post-initialization hook for Pydantic models."""
        pass

    @abstractmethod
    async def evaluate(
        self, agent_execution: AgentExecution, evaluation_criteria: T
    ) -> EvaluationResult:
        """Evaluate the given data and return a result.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult containing the score and details
        """
        pass
