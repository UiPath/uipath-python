"""Exact match evaluator for agent outputs."""

from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
)
from .output_evaluator import (
    OutputEvaluationCriteria,
    OutputEvaluator,
    OutputEvaluatorConfig,
)


class ExactMatchEvaluatorConfig(OutputEvaluatorConfig[OutputEvaluationCriteria]):
    """Configuration for the exact match evaluator."""

    name: str = "ExactMatchEvaluator"
    case_sensitive: bool = False
    negated: bool = False


class ExactMatchEvaluator(
    OutputEvaluator[OutputEvaluationCriteria, ExactMatchEvaluatorConfig, type(None)]  # type: ignore
):
    """Evaluator that performs exact structural matching between expected and actual outputs.

    This evaluator returns True if the actual output exactly matches the expected output
    after canonical JSON normalization, and False otherwise. Numbers are normalized
    to floats for consistent comparison.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.EXACT_MATCH.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output exactly matches expected output.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - agent_output: The actual output from the agent
                - agent_trace: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Boolean result indicating exact match (True/False)
        """
        actual_output = str(self._get_actual_output(agent_execution))
        expected_output = str(self._get_expected_output(evaluation_criteria))
        if not self.evaluator_config.case_sensitive:
            actual_output = actual_output.lower()
            expected_output = expected_output.lower()

        is_exact_match = actual_output == expected_output
        if self.evaluator_config.negated:
            is_exact_match = not is_exact_match

        return NumericEvaluationResult(
            score=float(is_exact_match),
        )
