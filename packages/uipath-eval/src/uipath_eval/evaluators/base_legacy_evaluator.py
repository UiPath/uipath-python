"""Base evaluator abstract class for agent evaluation."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import ConfigDict, Field

from ..models import EvaluationResult
from ..models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)
from .._helpers.helpers import track_evaluation_metrics
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluatorConfig,
    GenericBaseEvaluator,
)

__all__ = ["track_evaluation_metrics"]

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


class BaseLegacyEvaluator(
    GenericBaseEvaluator[LegacyEvaluationCriteria, T, str], Generic[T], ABC
):
    """Abstract base class for all legacy evaluators.

    Inherits from BaseEvaluator to share common evaluator infrastructure while maintaining
    legacy-specific fields and behavior.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Required Fields
    category: LegacyEvaluatorCategory = Field(...)
    type: LegacyEvaluatorType = Field(...)

    # Optional Fields
    file_name: str = Field(default="", alias="fileName")
    target_output_key: str = Field(default="*", alias="targetOutputKey")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

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

    async def validate_and_evaluate_criteria(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate the given data and return a result from a raw evaluation criteria."""
        criteria = self.validate_evaluation_criteria(evaluation_criteria)
        return await self.evaluate(agent_execution, criteria)

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
        """
        pass
