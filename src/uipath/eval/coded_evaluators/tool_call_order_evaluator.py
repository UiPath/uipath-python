"""Tool call order evaluator for validating correct sequence of tool calls."""

from .._helpers.coded_evaluators_helpers import (
    extract_tool_calls_names,
    generate_datapoint_id,
    tool_calls_order_score,
)
from ..models import AgentExecution, EvaluationResult, NumericEvaluationResult
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


class ToolCallOrderEvaluatorConfig(BaseEvaluatorConfig):
    """Configuration for the tool call count evaluator."""

    name: str = "ToolCallOrderEvaluator"
    strict: bool = False
    default_evaluation_criteria: ToolCallOrderEvaluationCriteria | None = None


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
            evaluator_name=self.evaluator_config.name,
            datapoint_id=generate_datapoint_id(agent_execution),
        )
