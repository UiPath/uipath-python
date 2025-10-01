"""Base class for all output evaluator configurations."""

import json
from typing import Any, TypeVar, Union

from pydantic import Field

from ..models import AgentExecution
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)


class OutputEvaluationCriteria(BaseEvaluationCriteria):
    """Base class for all output evaluation criteria."""

    expected_output: dict[str, Any] | str


T_OutputCriteria = TypeVar("T_OutputCriteria", bound=OutputEvaluationCriteria)


class OutputEvaluatorConfig(BaseEvaluatorConfig[T_OutputCriteria]):
    """Base class for all output evaluator configurations.

    Generic over T_OutputCriteria to allow subclasses to define their own
    specific output evaluation criteria types while maintaining type safety.
    """

    target_output_key: str = Field(
        default="*", description="Key to extract output from agent execution"
    )


C = TypeVar("C", bound=OutputEvaluatorConfig[Any])
J = TypeVar("J", bound=Union[str, None, BaseEvaluatorJustification])


class OutputEvaluator(BaseEvaluator[T_OutputCriteria, C, J]):
    """Abstract base class for all output evaluators.

    Generic Parameters:
        T_OutputCriteria: The output evaluation criteria type
        C: The output evaluator config type (bound to OutputEvaluatorConfig[T_OutputCriteria])
        J: The justification type
    """

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Get the actual output from the agent execution."""
        if self.evaluator_config.target_output_key != "*":
            return agent_execution.agent_output[self.evaluator_config.target_output_key]
        return agent_execution.agent_output

    def _get_expected_output(self, evaluation_criteria: T_OutputCriteria) -> Any:
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
