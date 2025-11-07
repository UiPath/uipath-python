"""Base class for all output evaluator configurations."""

import json
from typing import Any, TypeVar, Union

from pydantic import Field

from ..models import AgentExecution
from ..models.models import UiPathEvaluationError, UiPathEvaluationErrorCategory
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)


class OutputEvaluationCriteria(BaseEvaluationCriteria):
    """Base class for all output evaluation criteria."""

    expected_output: dict[str, Any] | str = Field(..., alias="expectedOutput")


T = TypeVar("T", bound=BaseEvaluationCriteria)
T_OutputCriteria = TypeVar("T_OutputCriteria", bound=OutputEvaluationCriteria)


class OutputEvaluatorConfig(BaseEvaluatorConfig[T]):
    """Base class for all output evaluator configurations.

    Generic over T to allow subclasses to define their own
    specific output evaluation criteria types while maintaining type safety.
    """

    target_output_key: str = Field(
        default="*", description="Key to extract output from agent execution"
    )


C = TypeVar("C", bound=OutputEvaluatorConfig[Any])
J = TypeVar("J", bound=Union[str, None, BaseEvaluatorJustification])


class BaseOutputEvaluator(BaseEvaluator[T, C, J]):
    """Abstract base class for all output evaluators.

    Generic Parameters:
        T_OutputCriteria: The output evaluation criteria type
        C: The output evaluator config type (bound to OutputEvaluatorConfig[T_OutputCriteria])
        J: The justification type
    """

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Get the actual output from the agent execution."""
        if self.evaluator_config.target_output_key != "*":
            try:
                return agent_execution.agent_output[
                    self.evaluator_config.target_output_key
                ]
            except KeyError as e:
                raise UiPathEvaluationError(
                    code="TARGET_OUTPUT_KEY_NOT_FOUND",
                    title="Target output key not found in actual output",
                    detail=f"Error: {e}",
                    category=UiPathEvaluationErrorCategory.USER,
                ) from e
        return agent_execution.agent_output

    def _get_full_expected_output(self, evaluation_criteria: T) -> Any:
        """Get the full expected output from the evaluation criteria."""
        raise UiPathEvaluationError(
            code="NOT_IMPLEMENTED",
            title="This method was not implemented by the subclass.",
            detail="This method was not implemented by the subclass.",
            category=UiPathEvaluationErrorCategory.SYSTEM,
        )

    def _get_expected_output(self, evaluation_criteria: T) -> Any:
        """Load the expected output from the evaluation criteria."""
        expected_output = self._get_full_expected_output(evaluation_criteria)
        if self.evaluator_config.target_output_key != "*":
            if isinstance(expected_output, str):
                try:
                    expected_output = json.loads(expected_output)
                except json.JSONDecodeError as e:
                    raise UiPathEvaluationError(
                        code="INVALID_EXPECTED_OUTPUT",
                        title="When target output key is not '*', expected output must be a dictionary or a valid JSON string",
                        detail=f"Error: {e}",
                        category=UiPathEvaluationErrorCategory.USER,
                    ) from e
            try:
                expected_output = expected_output[
                    self.evaluator_config.target_output_key
                ]
            except KeyError as e:
                raise UiPathEvaluationError(
                    code="TARGET_OUTPUT_KEY_NOT_FOUND",
                    title="Target output key not found in expected output",
                    detail=f"Error: {e}",
                    category=UiPathEvaluationErrorCategory.USER,
                ) from e
        return expected_output


class OutputEvaluator(BaseOutputEvaluator[T_OutputCriteria, C, J]):
    """Abstract base class for all output evaluators.

    Generic Parameters:
        T_OutputCriteria: The output evaluation criteria type
        C: The output evaluator config type (bound to OutputEvaluatorConfig[T_OutputCriteria])
        J: The justification type
    """

    def _get_full_expected_output(self, evaluation_criteria: T_OutputCriteria) -> Any:
        """Get the full expected output from the evaluation criteria."""
        return evaluation_criteria.expected_output
