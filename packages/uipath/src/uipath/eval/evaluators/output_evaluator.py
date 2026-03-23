"""Base class for all output evaluator configurations."""

import json
from typing import TYPE_CHECKING, Any, TypeVar, Union

from pydantic import BaseModel, Field

from .._helpers.output_path import resolve_output_path
from ..models import AgentExecution
from ..models.models import UiPathEvaluationError, UiPathEvaluationErrorCategory
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)

if TYPE_CHECKING:
    from ..models import EvaluationResult


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
    aggregation_method: str = "average"


class LineByLineEvaluationResult(BaseModel):
    """Container for line-by-line evaluation results.

    This is attached to the aggregated NumericEvaluationResult to allow
    the runtime to extract individual line results and store them separately.
    """

    model_config = {"arbitrary_types_allowed": True}

    line_results: list[tuple[int, Any]]  # (line_number, result)
    aggregation_method: str = "average"


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
        """Get the actual output from the agent execution."""
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

    def _split_into_lines(self, output: Any) -> list[str]:
        """Split output into lines using the configured delimiter.

        Args:
            output: The output to split (will be converted to string)

        Returns:
            List of lines (strings)
        """
        output_str = str(output)
        delimiter = self.evaluator_config.line_delimiter
        lines = output_str.split(delimiter)
        # Filter out empty lines
        return [line for line in lines if line.strip()]

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
        from ..models import NumericEvaluationResult

        # Get the full actual and expected outputs before splitting
        actual_output = self._get_actual_output(agent_execution)
        expected_output = self._get_expected_output(evaluation_criteria)

        # Split into lines
        actual_lines = self._split_into_lines(actual_output)
        expected_lines = self._split_into_lines(expected_output)

        # Store original agent execution data
        original_agent_output = agent_execution.agent_output

        # Evaluate each line
        line_results: list[tuple[int, "EvaluationResult"]] = []
        line_details = []
        max_lines = max(len(actual_lines), len(expected_lines))

        for i in range(max_lines):
            actual_line = actual_lines[i] if i < len(actual_lines) else ""
            expected_line = expected_lines[i] if i < len(expected_lines) else ""

            # Wrap lines in the same structure as original output for targetOutputKey
            # If targetOutputKey is "*", use the line directly
            # Otherwise, wrap it in a dict with the targetOutputKey
            line_agent_output: Any
            line_expected_output: Any
            if self.evaluator_config.target_output_key == "*":
                line_agent_output = actual_line
                line_expected_output = expected_line
            else:
                line_agent_output = {
                    self.evaluator_config.target_output_key: actual_line
                }
                line_expected_output = {
                    self.evaluator_config.target_output_key: expected_line
                }

            # Create a modified agent execution with this line as output
            line_agent_execution = AgentExecution(
                agent_input=agent_execution.agent_input,
                agent_output=line_agent_output,
                agent_trace=agent_execution.agent_trace,
                expected_agent_behavior=agent_execution.expected_agent_behavior,
                simulation_instructions=agent_execution.simulation_instructions,
            )

            # Create modified criteria with this line as expected output
            line_criteria_dict = evaluation_criteria.model_dump()
            if "expected_output" in line_criteria_dict:
                line_criteria_dict["expected_output"] = line_expected_output

            line_criteria = type(evaluation_criteria).model_validate(line_criteria_dict)

            # Evaluate this line
            line_result = await self.evaluate(line_agent_execution, line_criteria)
            line_results.append((i + 1, line_result))  # Store line number with result

            # Build line detail for summary
            line_detail = LineEvaluationDetail(
                line_number=i + 1,
                actual=actual_line,
                expected=expected_line,
                score=line_result.score,
                details=line_result.details
                if hasattr(line_result, "details")
                else None,
            )
            line_details.append(line_detail)

        # Restore original agent output
        agent_execution.agent_output = original_agent_output

        # Aggregate scores
        if not line_results:
            aggregated_score = 0.0
        else:
            scores = []
            for _line_num, result in line_results:
                if hasattr(result, "score"):
                    score = result.score
                    # Convert boolean to float
                    if isinstance(score, bool):
                        scores.append(1.0 if score else 0.0)
                    else:
                        scores.append(float(score))
            aggregated_score = sum(scores) / len(scores) if scores else 0.0

        # Build details with per-line summary
        details = LineByLineEvaluationDetails(
            line_by_line_results=line_details,
            total_lines_actual=len(actual_lines),
            total_lines_expected=len(expected_lines),
            aggregation_method="average",
        )

        # Create the aggregated result with line results attached
        aggregated_result = NumericEvaluationResult(
            score=aggregated_score,
            details=details,
        )

        # Attach line results container for runtime to extract
        # This allows storing each line result as a separate entry
        setattr(  # noqa: B010
            aggregated_result,
            "_line_by_line_results",
            LineByLineEvaluationResult(
                line_results=line_results, aggregation_method="average"
            ),
        )

        return aggregated_result


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
