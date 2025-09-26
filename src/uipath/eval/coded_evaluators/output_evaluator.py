"""Base class for all output evaluator configurations."""

import json
from typing import Any, TypeVar

from pydantic import Field

from ..models import AgentExecution
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
)


class OutputEvaluationCriteria(BaseEvaluationCriteria):
    """Base class for all output evaluation criteria."""

    expected_output: dict[str, Any] | str


class OutputEvaluatorConfig(BaseEvaluatorConfig):
    """Base class for all output evaluator configurations."""

    target_output_key: str = Field(
        default="*", description="Key to extract output from agent execution"
    )
    default_evaluation_criteria: OutputEvaluationCriteria | None = None


C = TypeVar("C", bound=OutputEvaluatorConfig)


class OutputEvaluator(BaseEvaluator[OutputEvaluationCriteria, C]):
    """Abstract base class for all output evaluators."""

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Get the actual output from the agent execution."""
        if self.evaluator_config.target_output_key != "*":
            return agent_execution.agent_output[self.evaluator_config.target_output_key]
        return agent_execution.agent_output

    def _get_expected_output(
        self, evaluation_criteria: OutputEvaluationCriteria
    ) -> Any:
        """Load the expected output from the evaluation criteria."""
        expected_output = evaluation_criteria.expected_output
        if self.evaluator_config.target_output_key != "*":
            if isinstance(expected_output, str):
                try:
                    expected_output = json.loads(expected_output)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        "When target output key is not '*', expected output must be a dictionary or a valid JSON string"
                    ) from e
            expected_output = expected_output[self.evaluator_config.target_output_key]
        return expected_output
