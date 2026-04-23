"""Base class for all output evaluator configurations."""

import json
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar, Union

from pydantic import BaseModel, Field

from .._helpers.output_path import resolve_output_path
from ..models import AgentExecution
from ..models.models import UiPathEvaluationError, UiPathEvaluationErrorCategory
from .attachment_utils import (
    download_attachment_as_string,
    extract_attachment_id,
    is_job_attachment_uri,
)
from uipath_eval.evaluators.output_evaluator import (
    OutputEvaluationCriteria as OutputEvaluationCriteria,
)

from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)
from .line_by_line_utils import (
    split_into_lines,
)

if TYPE_CHECKING:
    from ..models import EvaluationResult


class AggregationMethod(str, Enum):
    """Aggregation methods for line-by-line evaluation scores."""

    AVERAGE = "average"
    MAX = "max"
    MIN = "min"
    MEDIAN = "median"


class LineEvaluationDetail(BaseModel):
    """Details for a single line evaluation."""

    line_number: int
    actual: str
    expected: str
    score: float | bool
    details: Any = None


class LineByLineEvaluationDetails(BaseModel):
    """Aggregated details for line-by-line evaluation."""

    line_by_line_results: list[LineEvaluationDetail]
    total_lines_actual: int
    total_lines_expected: int
    aggregation_method: AggregationMethod = AggregationMethod.AVERAGE


class LineByLineEvaluationResult(BaseModel):
    """Container for line-by-line evaluation results.

    This is attached to the aggregated NumericEvaluationResult to allow
    the runtime to extract individual line results and store them separately.
    """

    model_config = {"arbitrary_types_allowed": True}

    line_results: list[tuple[int, Any]]  # (line_number, result)
    aggregation_method: AggregationMethod = AggregationMethod.AVERAGE


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
    line_by_line_evaluator: bool = Field(
        default=False,
        description="If True, split output by delimiter and evaluate each line separately",
    )
    line_delimiter: str = Field(
        default="\n",
        description="Delimiter to split output when line_by_line_evaluator is True",
    )


C = TypeVar("C", bound=OutputEvaluatorConfig[Any])
J = TypeVar("J", bound=Union[str, BaseEvaluatorJustification])


# NOTE: This evaluator is only used in coded evaluators
class BaseOutputEvaluator(BaseEvaluator[T, C, J]):
    """Abstract base class for all output evaluators.

    Generic Parameters:
        T_OutputCriteria: The output evaluation criteria type
        C: The output evaluator config type (bound to OutputEvaluatorConfig[T_OutputCriteria])
        J: The justification type
    """

    def _normalize_numbers(self, obj: Any) -> Any:
        """Recursively normalize int/float to float for consistent numeric comparison.

        Converts all numeric values (int, float) to float in nested structures
        (dicts, lists), while preserving booleans and other data types.
        """
        if isinstance(obj, dict):
            return {k: self._normalize_numbers(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._normalize_numbers(v) for v in obj]
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return float(obj)
        return obj

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Get the actual output from the agent execution.

        If the output is a job attachment URI, downloads the attachment
        and returns its content as a string.
        """
        if self.evaluator_config.target_output_key != "*":
            try:
                result = resolve_output_path(
                    agent_execution.agent_output,
                    self.evaluator_config.target_output_key,
                )
            except (KeyError, IndexError, TypeError) as e:
                raise UiPathEvaluationError(
                    code="TARGET_OUTPUT_KEY_NOT_FOUND",
                    title="Target output key not found in actual output",
                    detail=f"Error: {e}",
                    category=UiPathEvaluationErrorCategory.USER,
                ) from e
        else:
            result = agent_execution.agent_output

        # Check if result is a job attachment URI and download if so
        if is_job_attachment_uri(result):
            attachment_id = extract_attachment_id(result)
            result = download_attachment_as_string(attachment_id)

        return self._normalize_numbers(result)

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
                expected_output = resolve_output_path(
                    expected_output,
                    self.evaluator_config.target_output_key,
                )
            except (KeyError, IndexError, TypeError) as e:
                raise UiPathEvaluationError(
                    code="TARGET_OUTPUT_KEY_NOT_FOUND",
                    title="Target output key not found in expected output",
                    detail=f"Error: {e}",
                    category=UiPathEvaluationErrorCategory.USER,
                ) from e
        return self._normalize_numbers(expected_output)

    async def validate_and_evaluate_criteria(
        self,
        agent_execution: "AgentExecution",
        evaluation_criteria: Any,
    ) -> "EvaluationResult":
        """Validate evaluation criteria and evaluate the agent execution.

        If line_by_line_evaluator is enabled, splits the output by delimiter
        and evaluates each line separately, then aggregates the scores.

        Args:
            agent_execution: The agent execution to evaluate
            evaluation_criteria: The evaluation criteria (dict or typed object)

        Returns:
            EvaluationResult with aggregated score if line-by-line, else single score
        """
        # Validate criteria first
        if evaluation_criteria is None:
            evaluation_criteria = self.evaluator_config.default_evaluation_criteria

        if evaluation_criteria is None:
            raise UiPathEvaluationError(
                code="MISSING_EVALUATION_CRITERIA",
                title="No evaluation criteria provided",
                detail="Evaluation criteria must be provided either in the request or as default in config",
                category=UiPathEvaluationErrorCategory.USER,
            )

        validated_criteria = self.validate_evaluation_criteria(evaluation_criteria)

        # Check if line-by-line evaluation is enabled
        if not self.evaluator_config.line_by_line_evaluator:
            # Standard evaluation
            return await self.evaluate(agent_execution, validated_criteria)

        # Line-by-line evaluation
        return await self._evaluate_line_by_line(agent_execution, validated_criteria)

    async def _evaluate_line_by_line(
        self,
        agent_execution: "AgentExecution",
        evaluation_criteria: T,
    ) -> "EvaluationResult":
        """Evaluate output line by line and aggregate scores.

        Args:
            agent_execution: The agent execution to evaluate
            evaluation_criteria: Validated evaluation criteria

        Returns:
            NumericEvaluationResult with aggregated score
        """
        from .line_by_line_utils import build_line_by_line_result, evaluate_lines

        # Get the full actual and expected outputs before splitting
        actual_output = self._get_actual_output(agent_execution)
        expected_output = self._get_expected_output(evaluation_criteria)

        # Split into lines using utility function
        actual_lines = split_into_lines(
            actual_output,
            self.evaluator_config.line_delimiter,
            self.evaluator_config.target_output_key,
        )
        expected_lines = split_into_lines(
            expected_output,
            self.evaluator_config.line_delimiter,
            self.evaluator_config.target_output_key,
        )

        # Store original agent execution data
        original_agent_output = agent_execution.agent_output

        # Create function to build line criteria
        def create_line_criteria(expected_line: str) -> Any:
            from .line_by_line_utils import wrap_line_in_structure

            line_expected_output = wrap_line_in_structure(
                expected_line, self.evaluator_config.target_output_key
            )
            line_criteria_dict = evaluation_criteria.model_dump()
            if "expected_output" in line_criteria_dict:
                line_criteria_dict["expected_output"] = line_expected_output
            return type(evaluation_criteria).model_validate(line_criteria_dict)

        # Evaluate all lines using utility function
        line_details, line_results = await evaluate_lines(
            actual_lines=actual_lines,
            expected_lines=expected_lines,
            target_output_key=self.evaluator_config.target_output_key,
            agent_execution=agent_execution,
            evaluate_fn=self.evaluate,
            create_line_criteria_fn=create_line_criteria,
        )

        # Restore original agent output
        agent_execution.agent_output = original_agent_output

        # Build and return the aggregated result using utility function
        return build_line_by_line_result(
            line_details=line_details,
            line_results=line_results,
            actual_lines=actual_lines,
            expected_lines=expected_lines,
        )


# NOTE: This evaluator is only used in coded evaluators.
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
