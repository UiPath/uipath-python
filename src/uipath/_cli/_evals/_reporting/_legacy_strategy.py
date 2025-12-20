"""Legacy evaluation reporting strategy.

This module implements the strategy for legacy evaluation reporting,
which uses assertionRuns format and converts string IDs to GUIDs.
"""

import uuid
from typing import Any, Callable

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot
from uipath.eval.evaluators import LegacyBaseEvaluator


class LegacyEvalReportingStrategy:
    """Strategy for legacy evaluation reporting.

    Legacy evaluations:
    - Convert string IDs to deterministic GUIDs using uuid5
    - Use endpoints without /coded/ prefix
    - Use assertionRuns format with assertionSnapshot
    - Put expectedOutput directly in evalSnapshot
    """

    @property
    def endpoint_suffix(self) -> str:
        """Return empty string for legacy endpoints (no /coded/ prefix)."""
        return ""

    def convert_id(self, id_value: str) -> str:
        """Convert string ID to deterministic GUID for legacy API.

        Args:
            id_value: The original string ID

        Returns:
            The ID as a GUID (either original if valid, or deterministic uuid5)
        """
        try:
            uuid.UUID(id_value)
            return id_value
        except ValueError:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_value))

    def create_eval_set_run_payload(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        project_id: str,
    ) -> dict[str, Any]:
        """Create payload for creating a legacy eval set run."""
        return {
            "agentId": project_id,
            "evalSetId": self.convert_id(eval_set_id),
            "agentSnapshot": agent_snapshot.model_dump(by_alias=True),
            "status": EvaluationStatus.IN_PROGRESS.value,
            "numberOfEvalsExecuted": no_of_evals,
            "source": 0,  # EvalRunSource.Manual
        }

    def create_eval_run_payload(
        self,
        eval_item: EvaluationItem,
        eval_set_run_id: str,
    ) -> dict[str, Any]:
        """Create payload for creating a legacy eval run."""
        eval_item_id = self.convert_id(eval_item.id)

        # Extract expectedOutput from evaluation_criterias
        expected_output = {}
        if eval_item.evaluation_criterias:
            first_criteria = next(iter(eval_item.evaluation_criterias.values()), None)
            if first_criteria and isinstance(first_criteria, dict):
                expected_output = first_criteria.get("expectedOutput", {})

        return {
            "evalSetRunId": eval_set_run_id,
            "evalSnapshot": {
                "id": eval_item_id,
                "name": eval_item.name,
                "inputs": eval_item.inputs,
                "expectedOutput": expected_output,
            },
            "status": EvaluationStatus.IN_PROGRESS.value,
        }

    def create_update_eval_run_payload(
        self,
        eval_run_id: str,
        evaluator_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
    ) -> dict[str, Any]:
        """Create payload for updating a legacy eval run."""
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED
        return {
            "evalRunId": eval_run_id,
            "status": status.value,
            "result": {
                "output": dict(actual_output),
                "evaluatorScores": evaluator_scores,
            },
            "completionMetrics": {"duration": int(execution_time)},
            "assertionRuns": evaluator_runs,
        }

    def create_update_eval_set_run_payload(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        success: bool,
    ) -> dict[str, Any]:
        """Create payload for updating a legacy eval set run."""
        scores_list = [
            {"value": avg_score, "evaluatorId": self.convert_id(eval_id)}
            for eval_id, avg_score in evaluator_scores.items()
        ]
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED
        return {
            "evalSetRunId": eval_set_run_id,
            "status": status.value,
            "evaluatorScores": scores_list,
        }

    def collect_results(
        self,
        eval_results: list[Any],
        evaluators: dict[str, LegacyBaseEvaluator[Any]],
        usage_metrics: dict[str, int | float | None],
        serialize_justification_fn: Callable[[Any], str | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results in legacy assertionRuns format."""
        assertion_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        for eval_result in eval_results:
            if eval_result.evaluator_id not in evaluators:
                continue

            evaluator_id_value = self.convert_id(eval_result.evaluator_id)
            evaluator = evaluators[eval_result.evaluator_id]
            justification = serialize_justification_fn(eval_result.result.details)

            evaluator_scores_list.append(
                {
                    "type": eval_result.result.score_type.value,
                    "value": eval_result.result.score,
                    "justification": justification,
                    "evaluatorId": evaluator_id_value,
                }
            )

            assertion_runs.append(
                {
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorId": evaluator_id_value,
                    "completionMetrics": {
                        "duration": int(eval_result.result.evaluation_time or 0),
                        "cost": usage_metrics["cost"],
                        "tokens": usage_metrics["tokens"] or 0,
                        "completionTokens": usage_metrics["completionTokens"] or 0,
                        "promptTokens": usage_metrics["promptTokens"] or 0,
                    },
                    "assertionSnapshot": {
                        "assertionType": evaluator.evaluator_type.name,
                        "outputKey": evaluator.target_output_key,
                    },
                }
            )

        return assertion_runs, evaluator_scores_list
