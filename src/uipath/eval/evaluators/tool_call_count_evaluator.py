"""Tool call count evaluator for validating expected tool usage patterns."""

from collections import Counter

from .._helpers.evaluators_helpers import (
    extract_tool_calls_names,
    tool_calls_count_score,
)
from ..models import AgentExecution, EvaluationResult, NumericEvaluationResult
from ..models.models import EvaluatorType
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)


class ToolCallCountEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the tool call count evaluator."""

    # TODO: str field needs to be validated against some criteria that allows ">x", "<x", ">=x", "<=x", "x"
    tool_calls_count: dict[str, tuple[str, int]]


class ToolCallCountEvaluatorConfig(
    BaseEvaluatorConfig[ToolCallCountEvaluationCriteria]
):
    """Configuration for the tool call count evaluator."""

    name: str = "ToolCallCountEvaluator"
    strict: bool = False


class ToolCallCountEvaluatorJustification(BaseEvaluatorJustification):
    """Justification for the tool call count evaluator."""

    explained_tool_calls_count: dict[str, str]


class ToolCallCountEvaluator(
    BaseEvaluator[
        ToolCallCountEvaluationCriteria,
        ToolCallCountEvaluatorConfig,
        ToolCallCountEvaluatorJustification,
    ]
):
    """Evaluator that checks if the tool calls match the expected count.

    This evaluator returns a score based on how well the actual tool call counts
    match the expected counts specified in the criteria.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.TOOL_CALL_COUNT.value

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
        validated_justification = self.validate_justification(justification)
        return NumericEvaluationResult(
            score=score,
            details=validated_justification,
        )
