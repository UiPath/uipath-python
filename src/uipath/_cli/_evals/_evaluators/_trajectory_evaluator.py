from typing import Any, Dict

from .._models import EvaluationResult
from ._evaluator_base import EvaluatorBase


class TrajectoryEvaluator(EvaluatorBase):
    """Evaluator that analyzes the trajectory/path taken to reach outputs."""

    def __init__(
        self,
        trajectory_config: Dict[str, Any],
        step_weights: Dict[str, float],
        target_output_key: str = "*",
    ):
        """Initialize the trajectory evaluator.

        Args:
            trajectory_config: Configuration for trajectory analysis
            step_weights: Weights for different steps in the trajectory
            target_output_key: Key in output to evaluate ("*" for entire output)
        """
        super().__init__()
        self.trajectory_config = trajectory_config or {}
        self.step_weights = step_weights or {}
        self.target_output_key = target_output_key

    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate using trajectory analysis.

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
