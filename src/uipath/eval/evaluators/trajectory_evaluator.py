"""Trajectory evaluator for analyzing execution paths and decision sequences."""

from typing import TypeVar

from uipath.eval.models import EvaluationResult

from ..models.models import AgentExecution
from .base_evaluator import BaseEvaluator

T = TypeVar("T")


class TrajectoryEvaluator(BaseEvaluator[T]):
    """Evaluator that analyzes the trajectory/path taken to reach outputs."""

    async def evaluate(
        self, agent_execution: AgentExecution, evaluation_criteria: T
    ) -> EvaluationResult:
        """Evaluate using trajectory analysis.

        Analyzes the execution path and decision sequence taken by the agent
        to assess the quality of the reasoning process.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate
        Returns:
            EvaluationResult: Score based on trajectory analysis

        Raises:
            NotImplementedError: This evaluator is not yet implemented
        """
        raise NotImplementedError()
