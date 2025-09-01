"""Exact match evaluator for binary pass/fail evaluation of agent outputs."""

from typing import Any, Dict, Optional, TypeVar

from uipath.eval.models import EvaluationResult, ScoreType
from uipath.tracing import UiPathEvalSpan

from .deterministic_evaluator_base import DeterministicEvaluatorBase

T = TypeVar('T')

class ExactMatchEvaluator(DeterministicEvaluatorBase[T]):
    """Evaluator that performs exact structural matching between expected and actual outputs.

    This evaluator returns True if the actual output exactly matches the expected output
    after canonical JSON normalization, and False otherwise. Numbers are normalized
    to floats for consistent comparison.
    """

    def __init__(
        self,
        name: str = "ExactMatchEvaluator",
        description: Optional[str] = None,
        target_output_key: str = "*",
    ):
        """Initialize the ExactMatchEvaluator.

        Args:
            name: Display name for the evaluator
            description: Optional description of the evaluator's purpose
            target_output_key: Key to target in output for evaluation ("*" for entire output)
        """
        super().__init__(
            name=name, description=description, target_output_key=target_output_key
        )

    async def evaluate(
        self,
        agent_input: Optional[Dict[str, Any]],
        evaluation_criteria: T,
        actual_output: Dict[str, Any],
        uipath_eval_spans: Optional[list[UiPathEvalSpan]],
        execution_logs: str,
    ) -> EvaluationResult:
        """Evaluate whether actual output exactly matches expected output.

        Args:
            agent_input: The input provided to the agent (unused)
            evaluation_criteria: The evaluation criteria to evaluate
            actual_output: The actual output from the agent
            uipath_eval_spans: Execution spans from the agent (unused)
            execution_logs: Agent execution logs (unused)

        Returns:
            EvaluationResult: Boolean result indicating exact match (True/False)
        """
        try:
            are_equal = self._canonical_json(actual_output) == self._canonical_json(
                evaluation_criteria
            )

            return EvaluationResult(
                score=are_equal,
                score_type=ScoreType.BOOLEAN,
            )
        except Exception as e:
            return EvaluationResult(
                score=False,
                details=f"Error during evaluation: {str(e)}",
                score_type=ScoreType.ERROR,
            )
