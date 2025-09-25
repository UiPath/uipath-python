"""Tool call count evaluator for validating expected tool usage patterns."""

from collections import Counter

from .._helpers.helpers import (
    extract_tool_calls_names,
    tool_calls_count_score,
)
from ..models import AgentExecution, EvaluationResult, NumericEvaluationResult
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
)


class ToolCallCountEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the tool call count evaluator."""

    # TODO: str field needs to be validated against some criteria that allows ">x", "<x", ">=x", "<=x", "x"
    tool_calls_count: dict[str, tuple[str, int]]


class ToolCallCountEvaluatorConfig(BaseEvaluatorConfig):
    """Configuration for the tool call count evaluator."""

    name: str = "ToolCallCountEvaluator"
    strict: bool = False
    default_evaluation_criteria: ToolCallCountEvaluationCriteria | None = None


class ToolCallCountEvaluator(
    BaseEvaluator[ToolCallCountEvaluationCriteria, ToolCallCountEvaluatorConfig]
):
    """Evaluator that checks if the tool calls match the expected count.

    This evaluator returns a score based on how well the actual tool call counts
    match the expected counts specified in the criteria.
    """

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: ToolCallCountEvaluationCriteria,
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
        tool_calls_count = Counter(
            extract_tool_calls_names(agent_execution.agent_trace)
        )
        score, justification = tool_calls_count_score(
            tool_calls_count,
            evaluation_criteria.tool_calls_count,
            self.evaluator_config.strict,
        )
        return NumericEvaluationResult(
            score=score,
            details=justification,
        )
