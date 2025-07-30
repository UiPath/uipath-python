from typing import Any, Dict

from .._models import EvaluationResult
from ._evaluator_base import EvaluatorBase


class AgentScorerEvaluator(EvaluatorBase):
    """Evaluator that uses an agent to score outputs."""

    def __init__(
        self,
        agent_config: Dict[str, Any],
        scoring_criteria: Dict[str, Any],
        target_output_key: str = "*",
    ):
        """Initialize the agent scorer evaluator.

        Args:
            agent_config: Configuration for the scoring agent
            scoring_criteria: Criteria used for scoring
            target_output_key: Key in output to evaluate ("*" for entire output)
        """
        super().__init__()
        self.agent_config = agent_config or {}
        self.scoring_criteria = scoring_criteria or {}
        self.target_output_key = target_output_key

    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate using an agent scorer.

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
