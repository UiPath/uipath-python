"""Base evaluator abstract class for agent evaluation."""

import functools
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from pydantic import ConfigDict, Field

from ..models import EvaluationResult
from ..models.models import (
    AgentExecution,
    ErrorEvaluationResult,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluatorConfig,
    GenericBaseEvaluator,
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

    # Line-by-line evaluation support
    line_by_line_evaluation: bool = Field(default=False, alias="lineByLineEvaluation")
    line_delimiter: str = Field(default="\n", alias="lineDelimiter")

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

        # Check if line-by-line evaluation is enabled
        if self.line_by_line_evaluation:
            return await self._evaluate_line_by_line(agent_execution, criteria)

        return await self.evaluate(agent_execution, criteria)

    async def _evaluate_line_by_line(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate output line-by-line and aggregate results.

        Args:
            agent_execution: The execution details
            evaluation_criteria: The evaluation criteria

        Returns:
            Aggregated NumericEvaluationResult with line-by-line details
        """
        from ..models.models import NumericEvaluationResult
        from .output_evaluator import (
            LineByLineEvaluationDetails,
            LineByLineEvaluationResult,
            LineEvaluationDetail,
        )

        # Extract actual and expected outputs
        actual_output = self._get_actual_output(agent_execution)
        expected_output = evaluation_criteria.expected_output

        # Split into lines
        actual_lines = self._split_into_lines(actual_output)
        expected_lines = self._split_into_lines(expected_output)

        # Evaluate each line
        line_results: list[LineEvaluationDetail] = []
        line_evaluation_results: list[tuple[int, Any]] = []

        max_lines = max(len(actual_lines), len(expected_lines))

        for i in range(max_lines):
            actual_line = actual_lines[i] if i < len(actual_lines) else ""
            expected_line = expected_lines[i] if i < len(expected_lines) else ""

            # Wrap lines in the same structure as original output for target_output_key
            # If target_output_key is "*", use the line directly
            # Otherwise, wrap it in a dict with the target_output_key
            line_agent_output: Any
            line_expected_output: Any
            if self.target_output_key == "*":
                line_agent_output = actual_line
                line_expected_output = expected_line
            else:
                line_agent_output = {self.target_output_key: actual_line}
                line_expected_output = {self.target_output_key: expected_line}

            # Create a modified agent execution for this line
            line_agent_execution = AgentExecution(
                agent_input=agent_execution.agent_input,
                agent_output=line_agent_output,
                agent_trace=agent_execution.agent_trace,
            )

            # Create modified criteria for this line
            line_criteria = LegacyEvaluationCriteria(
                expected_output=line_expected_output,
                expected_agent_behavior=evaluation_criteria.expected_agent_behavior,
            )

            # Evaluate this line
            line_result = await self.evaluate(line_agent_execution, line_criteria)

            # Store line evaluation detail
            score_value = line_result.score if hasattr(line_result, "score") else 0.0
            line_results.append(
                LineEvaluationDetail(
                    line_number=i + 1,
                    actual=actual_line,
                    expected=expected_line,
                    score=score_value,
                    details=line_result.details
                    if hasattr(line_result, "details")
                    else None,
                )
            )

            # Store for runtime extraction with evaluator name suffix
            line_evaluation_results.append((i + 1, line_result))

        # Calculate aggregate score (average of all line scores)
        numeric_scores = [
            float(detail.score)
            for detail in line_results
            if isinstance(detail.score, (int, float))
        ]
        aggregate_score = (
            sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0.0
        )

        # Create aggregated details
        line_by_line_details = LineByLineEvaluationDetails(
            line_by_line_results=line_results,
            total_lines_actual=len(actual_lines),
            total_lines_expected=len(expected_lines),
            aggregation_method="average",
        )

        # Create line-by-line result container for runtime
        line_by_line_result = LineByLineEvaluationResult(
            line_results=line_evaluation_results,
            aggregation_method="average",
        )

        # Return aggregated result with line-by-line details attached
        aggregated_result = NumericEvaluationResult(
            score=aggregate_score,
            details=line_by_line_details,
        )

        # Attach line-by-line results for runtime extraction
        # This allows storing each line result as a separate entry
        setattr(  # noqa: B010
            aggregated_result,
            "_line_by_line_results",
            line_by_line_result,
        )

        return aggregated_result

    def _split_into_lines(self, text: Any) -> list[str]:
        """Split text into lines using the configured delimiter.

        Args:
            text: The text to split (can be str or dict)

        Returns:
            List of lines
        """
        # Handle dict case (when target_output_key != "*")
        if isinstance(text, dict) and self.target_output_key in text:
            text = text[self.target_output_key]

        # Convert to string if needed
        if not isinstance(text, str):
            text = str(text)

        # Split by delimiter
        lines = text.split(self.line_delimiter)

        return lines

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Extract actual output from agent execution.

        Args:
            agent_execution: The agent execution

        Returns:
            The actual output (either the full agent_output or a specific key)
        """
        agent_output = agent_execution.agent_output

        # If target_output_key is "*", return full output
        if self.target_output_key == "*":
            return agent_output

        # Otherwise, extract specific key
        if isinstance(agent_output, dict) and self.target_output_key in agent_output:
            return agent_output[self.target_output_key]

        # Fallback to full output
        return agent_output

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
