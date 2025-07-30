from typing import Any, Dict

from .._models import EvaluationResult
from ._evaluator_base import EvaluatorBase


class DeterministicEvaluator(EvaluatorBase):
    """Evaluator for deterministic/rule-based evaluations."""

    def __init__(self, rule_config: Dict[str, Any], target_output_key: str = "*"):
        """Initialize the deterministic evaluator.

        Args:
            rule_config: Configuration for the rule (expected_value, regex_pattern, etc.)
            target_output_key: Key in output to evaluate ("*" for entire output)
        """
        super().__init__()
        self.rule_config = rule_config or {}
        self.target_output_key = target_output_key

    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate using deterministic rules.

        Args:
            evaluation_id: The ID of the evaluation being processed
            evaluation_name: The name of the evaluation
            input_data: The input data for the evaluation
            expected_output: The expected output
            actual_output: The actual output from the agent

        Returns:
            EvaluationResult containing the score and details
        """
        raise NotImplementedError()
