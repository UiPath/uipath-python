"""Contains evaluator for agent outputs."""

import logging

from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
)
from .base_evaluator import BaseEvaluationCriteria
from .output_evaluator import (
    OutputEvaluator,
    OutputEvaluatorConfig,
)

logger = logging.getLogger(__name__)


class ContainsEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the contains evaluator."""

    search_text: str


class ContainsEvaluatorConfig(OutputEvaluatorConfig[ContainsEvaluationCriteria]):
    """Configuration for the contains evaluator."""

    name: str = "ContainsEvaluator"
    case_sensitive: bool = False
    negated: bool = False


class ContainsEvaluator(
    OutputEvaluator[ContainsEvaluationCriteria, ContainsEvaluatorConfig, type(None)]  # type: ignore
):
    """Evaluator that checks if the actual output contains the expected output.

    This evaluator returns True if the actual output contains the expected output,
    and False otherwise. It supports case sensitivity and negation options.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.CONTAINS.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: ContainsEvaluationCriteria,
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
        actual_output = str(self._get_actual_output(agent_execution, evaluation_criteria))
        expected_output = str(self._get_expected_output(evaluation_criteria))

        # Debug logging (before case conversion)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("\n" + "="*80)
            logger.debug("[DEBUG] ContainsEvaluator - Comparison:")
            logger.debug("="*80)
            logger.debug("[ACTUAL OUTPUT (original)]:\n%s", actual_output)
            logger.debug("\n" + "-"*80)
            logger.debug("[EXPECTED OUTPUT (original)]:\n%s", expected_output)
            logger.debug("-"*80)

        if not self.evaluator_config.case_sensitive:
            actual_output = actual_output.lower()
            expected_output = expected_output.lower()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("[ACTUAL OUTPUT (lowercased)]:\n%s", actual_output)
                logger.debug("\n" + "-"*80)
                logger.debug("[EXPECTED OUTPUT (lowercased)]:\n%s", expected_output)
                logger.debug("-"*80)

        is_contains = expected_output in actual_output

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[CASE SENSITIVE]: %s", self.evaluator_config.case_sensitive)
            logger.debug("[NEGATED]: %s", self.evaluator_config.negated)
            logger.debug("[CONTAINS RESULT]: %s", is_contains)

        if self.evaluator_config.negated:
            is_contains = not is_contains
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("[FINAL RESULT (after negation)]: %s", is_contains)
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("[FINAL RESULT]: %s", is_contains)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("="*80 + "\n")

        return NumericEvaluationResult(
            score=float(is_contains),
        )

    def _get_expected_output(
        self, evaluation_criteria: ContainsEvaluationCriteria
    ) -> str:
        """Get the expected output from the evaluation criteria."""
        return evaluation_criteria.search_text
