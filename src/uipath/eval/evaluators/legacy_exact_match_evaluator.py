"""Exact match evaluator for binary pass/fail evaluation of agent outputs."""

from uipath.eval.models import BooleanEvaluationResult, EvaluationResult

from ..models.models import AgentExecution
from .legacy_base_evaluator import LegacyEvaluationCriteria, LegacyEvaluatorConfig
from .legacy_deterministic_evaluator_base import DeterministicEvaluatorBase


class LegacyExactMatchEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy exact-match evaluators."""

    name: str = "LegacyExactMatchEvaluator"


class LegacyExactMatchEvaluator(
    DeterministicEvaluatorBase[LegacyExactMatchEvaluatorConfig]
):
    """Evaluator that performs exact structural matching between expected and actual outputs.

    This evaluator returns True if the actual output exactly matches the expected output
    after canonical JSON normalization, and False otherwise. Numbers are normalized
    to floats for consistent comparison.
    """

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output exactly matches expected output.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Boolean result indicating exact match (True/False)
        """
        actual_output = agent_execution.agent_output
        expected_output = evaluation_criteria.expected_output

        if self.target_output_key and self.target_output_key != "*":
            if isinstance(actual_output, dict) and isinstance(expected_output, dict):
                if not (
                    self.target_output_key in actual_output
                    and self.target_output_key in expected_output
                ):
                    # Assuming that we should pass the test.
                    expected_output = actual_output = {}
                else:
                    if self.target_output_key in actual_output:
                        actual_output = actual_output[self.target_output_key]
                    if self.target_output_key in expected_output:
                        expected_output = expected_output[self.target_output_key]

        return BooleanEvaluationResult(
            score=self._canonical_json(actual_output)
            == self._canonical_json(expected_output)
        )
