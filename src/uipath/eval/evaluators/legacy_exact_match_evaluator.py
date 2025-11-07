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
        return BooleanEvaluationResult(
            score=self._canonical_json(agent_execution.agent_output)
            == self._canonical_json(evaluation_criteria.expected_output)
        )
