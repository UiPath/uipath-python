"""Trajectory evaluator for analyzing execution paths and decision sequences."""

from typing import Any, Dict, Optional

from uipath.eval.models import EvaluationResult
from uipath.tracing import UiPathEvalSpan

from .base_evaluator import BaseEvaluator


class TrajectoryEvaluator(BaseEvaluator):
    """Evaluator that analyzes the trajectory/path taken to reach outputs."""

    def __init__(
        self,
        name: str = "TrajectoryEvaluator",
        description: Optional[str] = None,
        target_output_key: str = "*",
    ):
        """Initialize the TrajectoryEvaluator.

        Args:
            name: Display name for the evaluator
            description: Optional description of the evaluator's purpose
            target_output_key: Key to target in output for evaluation ("*" for entire output)
        """
        super().__init__(name, description)
        self.target_output_key = target_output_key

    async def evaluate(
        self,
        agent_input: Optional[Dict[str, Any]],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
        uipath_eval_spans: Optional[list[UiPathEvalSpan]],
        execution_logs: str,
    ) -> EvaluationResult:
        """Evaluate using trajectory analysis.

        Analyzes the execution path and decision sequence taken by the agent
        to assess the quality of the reasoning process.

        Args:
            agent_input: The input provided to the agent
            expected_output: The expected output structure
            actual_output: The actual output from the agent
            uipath_eval_spans: Execution spans containing trajectory information
            execution_logs: Agent execution logs

        Returns:
            EvaluationResult: Score based on trajectory analysis

        Raises:
            NotImplementedError: This evaluator is not yet implemented
        """
        raise NotImplementedError()
