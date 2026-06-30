"""Base evaluator abstract class for agent evaluation."""

import functools
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from pydantic import ConfigDict, Field

from ..models import EvaluationResult
from ..models.models import (
    ErrorEvaluationResult,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
    WorkloadExecution,
)
from .attachment_utils import (
    download_attachment_as_string,
    extract_attachment_id,
    is_job_attachment_uri,
)
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluatorConfig,
    GenericBaseEvaluator,
)
from .line_by_line_utils import split_into_lines


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
        workload_execution: WorkloadExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate the given data and return a result from a raw evaluation criteria."""
        criteria = self.validate_evaluation_criteria(evaluation_criteria)

        # Check if line-by-line evaluation is enabled
        if self.line_by_line_evaluation:
            return await self._evaluate_line_by_line(workload_execution, criteria)

        return await self.evaluate(workload_execution, criteria)

    async def _evaluate_line_by_line(
        self,
        workload_execution: WorkloadExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate output line-by-line and aggregate results.

        Args:
            workload_execution: The execution details
            evaluation_criteria: The evaluation criteria

        Returns:
            Aggregated NumericEvaluationResult with line-by-line details
        """
        from .line_by_line_utils import build_line_by_line_result, evaluate_lines

        # Extract actual and expected outputs
        actual_output = self._get_actual_output(workload_execution)
        expected_output = evaluation_criteria.expected_output

        # Split into lines using utility function
        actual_lines = split_into_lines(
            actual_output, self.line_delimiter, self.target_output_key
        )
        expected_lines = split_into_lines(
            expected_output, self.line_delimiter, self.target_output_key
        )

        # Create function to build line criteria
        def create_line_criteria(expected_line: str) -> LegacyEvaluationCriteria:
            from .line_by_line_utils import wrap_line_in_structure

            line_expected_output = wrap_line_in_structure(
                expected_line, self.target_output_key
            )
            return LegacyEvaluationCriteria(
                expected_output=line_expected_output,
                expected_agent_behavior=evaluation_criteria.expected_agent_behavior,
            )

        # Evaluate all lines using utility function
        line_details, line_results = await evaluate_lines(
            actual_lines=actual_lines,
            expected_lines=expected_lines,
            target_output_key=self.target_output_key,
            workload_execution=workload_execution,
            evaluate_fn=self.evaluate,
            create_line_criteria_fn=create_line_criteria,
        )

        # Build and return the aggregated result using utility function
        return build_line_by_line_result(
            line_details=line_details,
            line_results=line_results,
            actual_lines=actual_lines,
            expected_lines=expected_lines,
        )

    def _get_actual_output(self, workload_execution: WorkloadExecution) -> Any:
        """Extract actual output from agent execution.

        If the output is a job attachment URI, downloads the attachment
        and returns its content as a string.

        Args:
            workload_execution: The agent execution

        Returns:
            The actual output (either the full workload_output or a specific key)
        """
        workload_output = workload_execution.workload_output

        # If target_output_key is "*", return full output
        if self.target_output_key == "*":
            result = workload_output
        # Otherwise, extract specific key
        elif isinstance(workload_output, dict) and self.target_output_key in workload_output:
            result = workload_output[self.target_output_key]
        else:
            # Fallback to full output
            result = workload_output

        # Check if result is a job attachment URI and download if so
        if is_job_attachment_uri(result):
            # At this point we know result is a string
            assert isinstance(result, str)
            attachment_id = extract_attachment_id(result)
            result = download_attachment_as_string(attachment_id)

        return result

    @abstractmethod
    async def evaluate(
        self,
        workload_execution: WorkloadExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate the given data and return a result.

        Args:
            workload_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate (legacy evaluators accept any type)

        Returns:
            EvaluationResult containing the score and details
        """
        pass
