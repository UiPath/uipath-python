"""Contains evaluator for agent outputs."""

from ..models import AgentExecution, EvaluationResult, NumericEvaluationResult
from .output_evaluator import (
    OutputEvaluationCriteria,
    OutputEvaluator,
    OutputEvaluatorConfig,
)


class ContainsEvaluatorConfig(OutputEvaluatorConfig):
    """Configuration for the exact match evaluator."""

    name: str = "ContainsEvaluator"
    case_sensitive: bool = False
    negated: bool = False


class ContainsEvaluator(OutputEvaluator[ContainsEvaluatorConfig]):
    """Evaluator that checks if the actual output contains the expected output.

    This evaluator returns True if the actual output contains the expected output,
    and False otherwise. It supports case sensitivity and negation options.
    """

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output contains the expected output.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - agent_output: The actual output from the agent
                - agent_trace: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Boolean result indicating if output contains expected value (True/False)
        """
        actual_output = str(self._get_actual_output(agent_execution))
        expected_output = str(self._get_expected_output(evaluation_criteria))

        if not self.evaluator_config.case_sensitive:
            actual_output = actual_output.lower()
            expected_output = expected_output.lower()

        is_contains = expected_output in actual_output

        if self.evaluator_config.negated:
            is_contains = not is_contains

        return NumericEvaluationResult(score=float(is_contains))
