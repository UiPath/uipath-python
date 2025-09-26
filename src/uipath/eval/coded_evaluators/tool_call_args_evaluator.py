"""Tool call order evaluator for validating correct sequence of tool calls."""

from .._helpers.helpers import (
    extract_tool_calls,
    tool_calls_args_score,
)
from ..models import AgentExecution, EvaluationResult, NumericEvaluationResult, ToolCall
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
)


class ToolCallArgsEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the tool call order evaluator."""

    # TODO: name field of ToolCall needs to be validated such that it contains only the tools available
    tool_calls: list[ToolCall]


class ToolCallArgsEvaluatorConfig(BaseEvaluatorConfig):
    """Configuration for the tool call count evaluator."""

    name: str = "ToolCallArgsEvaluator"
    strict: bool = False
    subset: bool = False
    default_evaluation_criteria: ToolCallArgsEvaluationCriteria | None = None


class ToolCallArgsEvaluator(
    BaseEvaluator[ToolCallArgsEvaluationCriteria, ToolCallArgsEvaluatorConfig]
):
    """Evaluator that checks if the tool calls are in the correct order.

    This evaluator returns True if the tool calls are in the correct order, and False otherwise.
    """

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: ToolCallArgsEvaluationCriteria,
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
        tool_calls_order = extract_tool_calls(agent_execution.agent_trace)
        score, justification = tool_calls_args_score(
            tool_calls_order,
            evaluation_criteria.tool_calls,
            self.evaluator_config.strict,
            self.evaluator_config.subset,
        )
        return NumericEvaluationResult(
            score=score,
            details=justification,
        )
