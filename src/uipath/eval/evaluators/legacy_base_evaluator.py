"""Base evaluator abstract class for agent evaluation."""

import functools
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from pydantic import ConfigDict, Field

from uipath.eval.models import EvaluationResult
from uipath.eval.models.models import (
    AgentExecution,
    ErrorEvaluationResult,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)

from .base_evaluator import BaseEvaluationCriteria, BaseEvaluator, BaseEvaluatorConfig


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


# Legacy evaluator config (non-generic version for simplicity)
class LegacyEvaluatorConfig(BaseEvaluatorConfig[BaseEvaluationCriteria]):
    """Configuration for legacy evaluators."""

    name: str = "LegacyEvaluator"
    default_evaluation_criteria: None = None  # Legacy evaluators don't use this


class LegacyEvaluationCriteria(BaseEvaluationCriteria):
    """Legacy evaluation criteria."""

    expected_output: Any = Field(alias="expectedOutput")
    expected_agent_behavior: str = Field(alias="expectedAgentBehavior")


T = TypeVar("T", bound=LegacyEvaluatorConfig)


class LegacyBaseEvaluator(
    BaseEvaluator[LegacyEvaluationCriteria, T, str], Generic[T], ABC
):
    """Abstract base class for all legacy evaluators.

    Inherits from BaseEvaluator to share common evaluator infrastructure while maintaining
    legacy-specific fields and behavior.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Legacy-specific fields (in addition to inherited fields from BaseEvaluator)
    target_output_key: str = "*"
    created_at: str
    updated_at: str
    category: LegacyEvaluatorCategory
    evaluator_type: LegacyEvaluatorType

    # Note: __init_subclass__ is inherited from BaseEvaluator and handles metrics tracking

    def model_post_init(self, __context: Any):
        """Post-initialization hook for Pydantic models."""
        # Ensure config is set up for legacy evaluators
        super().model_post_init(__context)

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id.

        For legacy evaluators, this returns a placeholder. Actual evaluator instances
        have an 'id' field that identifies them.
        """
        return "legacy-evaluator"

    @abstractmethod
    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate the given data and return a result.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate (legacy evaluators accept any type)

        Returns:
            EvaluationResult containing the score and details

        Note:
            The type: ignore[override] is necessary because legacy evaluators accept
            evaluation_criteria of any type T, while the base class expects BaseEvaluationCriteria.
            This is intentional to maintain backward compatibility with legacy evaluators.
        """
        pass
