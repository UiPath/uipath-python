"""Tool call order evaluator for validating correct sequence of tool calls."""

from .._helpers.evaluators_helpers import (
    extract_tool_calls_names,
    tool_calls_order_score,
)
from ..models import AgentExecution, EvaluationResult, NumericEvaluationResult
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

    actual_tool_calls_order: list[str]
    expected_tool_calls_order: list[str]
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
        agent_execution: AgentExecution,
        evaluation_criteria: ToolCallOrderEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate if the tool calls are in the correct order.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - agent_output: The final output of the agent
                - agent_trace: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate
        Returns:
            EvaluationResult: Boolean result indicating correct tool call order (True/False)
        """
        tool_calls_order = extract_tool_calls_names(agent_execution.agent_trace)
        score, justification = tool_calls_order_score(
            tool_calls_order,
            evaluation_criteria.tool_calls_order,
            self.evaluator_config.strict,
        )
        validated_justification = self.validate_justification(justification)
        return NumericEvaluationResult(
            score=score,
            details=validated_justification,
        )
