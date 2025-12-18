"""Coded agent payload builder for evaluation reporting."""

from typing import Any

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._payload_builders._base import BasePayloadBuilder
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import EvalItemResult


class CodedPayloadBuilder(BasePayloadBuilder):
    """Payload builder for coded agent evaluations.

    Coded agents use string IDs and the /coded/ endpoint suffix.
    The payload format includes evaluatorRuns with nested result objects.
    """

    @property
    def endpoint_suffix(self) -> str:
        """Coded evaluations use the /coded/ endpoint suffix."""
        return "coded/"

    def format_id(self, id_value: str) -> str:
        """Coded evaluations use string IDs directly."""
        return id_value

    def build_eval_snapshot(self, eval_item: EvaluationItem) -> dict[str, Any]:
        """Build eval snapshot with evaluationCriterias for coded agents.

        Args:
            eval_item: The evaluation item.

        Returns:
            Dict containing the eval snapshot with evaluationCriterias.
        """
        return {
            "id": eval_item.id,
            "name": eval_item.name,
            "inputs": eval_item.inputs,
            "evaluationCriterias": eval_item.evaluation_criterias,
        }

    def collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, BaseEvaluator[Any, Any, Any]],
        usage_metrics: dict[str, int | float | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results for coded evaluators.

        Returns evaluatorRuns with nested result objects and scores list.

        Args:
            eval_results: List of evaluation results.
            evaluators: Dict of evaluator ID to BaseEvaluator instance.
            usage_metrics: Token usage and cost metrics.

        Returns:
            Tuple of (evaluator_runs, evaluator_scores).
        """
        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores: list[dict[str, Any]] = []

        for eval_result in eval_results:
            if eval_result.evaluator_id not in evaluators:
                continue

            justification = self.serialize_justification(eval_result.result.details)

            evaluator_scores.append(
                {
                    "type": eval_result.result.score_type.value,
                    "value": eval_result.result.score,
                    "justification": justification,
                    "evaluatorId": eval_result.evaluator_id,
                }
            )

            evaluator_runs.append(
                {
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorId": eval_result.evaluator_id,
                    "result": {
                        "score": {
                            "type": eval_result.result.score_type.value,
                            "value": eval_result.result.score,
                        },
                        "justification": justification,
                    },
                    "completionMetrics": self.build_completion_metrics(
                        eval_result.result.evaluation_time, usage_metrics
                    ),
                }
            )

        return evaluator_runs, evaluator_scores

    def build_update_eval_run_payload(
        self,
        eval_run_id: str,
        runs: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
    ) -> dict[str, Any]:
        """Build update payload for coded evaluations.

        Coded format uses 'scores' and 'evaluatorRuns' keys.

        Args:
            eval_run_id: The evaluation run ID.
            runs: List of evaluator runs.
            scores: List of evaluator scores.
            actual_output: The agent's actual output.
            execution_time: Total execution time.
            success: Whether the evaluation succeeded.

        Returns:
            The payload dict.
        """
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED

        return {
            "evalRunId": eval_run_id,
            "status": status.value,
            "result": {
                "output": dict(actual_output),
                "scores": scores,
            },
            "completionMetrics": {"duration": int(execution_time)},
            "evaluatorRuns": runs,
        }
