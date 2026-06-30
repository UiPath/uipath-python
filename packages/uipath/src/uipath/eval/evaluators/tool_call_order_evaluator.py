"""Tool call order evaluator for validating correct sequence of tool calls."""

from .._helpers.evaluators_helpers import (
    extract_tool_calls,
    tool_calls_order_score_with_ids,
)
from ..models import EvaluationResult, NumericEvaluationResult, WorkloadExecution
from ..models.models import EvaluatorType
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)


class ToolCallOrderEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the tool call order evaluator."""

    # TODO: str field needs to be validated such that it contains only the tools available
    tool_calls_order: list[str]


class ToolCallOrderEvaluatorConfig(
    BaseEvaluatorConfig[ToolCallOrderEvaluationCriteria]
):
    """Configuration for the tool call count evaluator."""

    name: str = "ToolCallOrderEvaluator"
    strict: bool = False


class ToolCallOrderEvaluatorJustification(BaseEvaluatorJustification):
    """Justification for the tool call order evaluator."""

    lcs: list[str]


class ToolCallOrderEvaluator(
    BaseEvaluator[
        ToolCallOrderEvaluationCriteria,
        ToolCallOrderEvaluatorConfig,
        ToolCallOrderEvaluatorJustification,
    ]
):
    """Evaluator that checks if the tool calls are in the correct order.

    This evaluator returns True if the tool calls are in the correct order, and False otherwise.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.TOOL_CALL_ORDER.value

    async def evaluate(
        self,
        workload_execution: WorkloadExecution,
        evaluation_criteria: ToolCallOrderEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate if the tool calls are in the correct order.

        Args:
            workload_execution: The execution details containing:
                - agent_input: The input received by the agent
                - workload_output: The final output of the agent
                - workload_trace: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate
        Returns:
            EvaluationResult: Boolean result indicating correct tool call order (True/False)
        """
        actual_calls = extract_tool_calls(
            workload_execution.workload_trace, include_args=False
        )
        score, justification = tool_calls_order_score_with_ids(
            actual_calls,
            evaluation_criteria.tool_calls_order,
            self.evaluator_config.strict,
        )
        validated_justification = self.validate_justification(justification)
        return NumericEvaluationResult(
            score=score,
            details=validated_justification,
        )
