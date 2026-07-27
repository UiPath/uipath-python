"""Legacy (low-code) agent payload builder for evaluation reporting."""

from typing import Any

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._payload_builders._base import BasePayloadBuilder
from uipath.eval.evaluators import LegacyBaseEvaluator
from uipath.eval.models import EvalItemResult


class LegacyPayloadBuilder(BasePayloadBuilder):
    """Payload builder for legacy (low-code) agent evaluations.

    Legacy agents require GUIDs for IDs and use the base endpoint (no suffix).
    The payload format includes assertionRuns with assertionSnapshot objects.
    """

    @property
    def endpoint_suffix(self) -> str:
        """Legacy evaluations use no endpoint suffix."""
        return ""

    def format_id(self, id_value: str) -> str:
        """Legacy evaluations require GUID format.

        Converts string IDs to deterministic GUIDs using UUID5.
        """
        return self.try_parse_or_convert_guid(id_value)

    def build_eval_snapshot(self, eval_item: EvaluationItem) -> dict[str, Any]:
        """Build eval snapshot with expectedOutput for legacy agents.

        Legacy agents expect expectedOutput directly in the snapshot.
        Since eval items are migrated to EvaluationItem format, we extract
        expectedOutput from the first evaluator criteria.

        Args:
            eval_item: The evaluation item.

        Returns:
            Dict containing the eval snapshot with expectedOutput.
        """
        # Extract expectedOutput from migrated evaluationCriterias
        # All criteria have the same expectedOutput, so we take the first
        expected_output: dict[str, Any] = {}
        if eval_item.evaluation_criterias:
            first_criteria = next(iter(eval_item.evaluation_criterias.values()), None)
            if first_criteria and isinstance(first_criteria, dict):
                expected_output = first_criteria.get("expectedOutput", {})

        return {
            "id": self.format_id(eval_item.id),
            "name": eval_item.name,
            "inputs": eval_item.inputs,
            "expectedOutput": expected_output,
        }

    def collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, LegacyBaseEvaluator[Any]],
        usage_metrics: dict[str, int | float | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results for legacy evaluators.

        Returns assertionRuns with assertionSnapshot objects and scores list.

        Args:
            eval_results: List of evaluation results.
            evaluators: Dict of evaluator ID to LegacyBaseEvaluator instance.
            usage_metrics: Token usage and cost metrics.

        Returns:
            Tuple of (assertion_runs, evaluator_scores).
        """
        assertion_runs: list[dict[str, Any]] = []
        evaluator_scores: list[dict[str, Any]] = []

        for eval_result in eval_results:
            if eval_result.evaluator_id not in evaluators:
                continue

            evaluator_id_guid = self.format_id(eval_result.evaluator_id)
            justification = self.serialize_justification(eval_result.result.details)
            evaluator = evaluators[eval_result.evaluator_id]

            evaluator_scores.append(
                {
                    "type": eval_result.result.score_type.value,
                    "value": eval_result.result.score,
                    "justification": justification,
                    "evaluatorId": evaluator_id_guid,
                }
            )

            assertion_runs.append(
                {
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorId": evaluator_id_guid,
                    "completionMetrics": self.build_completion_metrics(
                        eval_result.result.evaluation_time, usage_metrics
                    ),
                    "assertionSnapshot": {
                        "assertionType": evaluator.evaluator_type.name,
                        "outputKey": evaluator.target_output_key,
                    },
                }
            )

        return assertion_runs, evaluator_scores

    def build_update_eval_run_payload(
        self,
        eval_run_id: str,
        runs: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
    ) -> dict[str, Any]:
        """Build update payload for legacy evaluations.

        Legacy format uses 'evaluatorScores' and 'assertionRuns' keys.

        Args:
            eval_run_id: The evaluation run ID.
            runs: List of assertion runs.
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
                "evaluatorScores": scores,
            },
            "completionMetrics": {"duration": int(execution_time)},
            "assertionRuns": runs,
        }
