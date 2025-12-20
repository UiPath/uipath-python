"""Coded evaluation reporting strategy.

This module implements the strategy for coded evaluation reporting,
which uses evaluatorRuns format and keeps string IDs unchanged.
"""

from typing import Any, Callable

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot
from uipath.eval.evaluators import BaseEvaluator


class CodedEvalReportingStrategy:
    """Strategy for coded evaluation reporting.

    Coded evaluations:
    - Keep string IDs unchanged
    - Use endpoints with /coded/ prefix
    - Use evaluatorRuns format with nested result
    - Put evaluationCriterias in evalSnapshot
    """

    @property
    def endpoint_suffix(self) -> str:
        """Return 'coded/' for coded endpoints."""
        return "coded/"

    def convert_id(self, id_value: str) -> str:
        """Keep string ID unchanged for coded API."""
        return id_value

    def create_eval_set_run_payload(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        project_id: str,
    ) -> dict[str, Any]:
        """Create payload for creating a coded eval set run."""
        return {
            "agentId": project_id,
            "evalSetId": eval_set_id,
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
        """Create payload for creating a coded eval run."""
        return {
            "evalSetRunId": eval_set_run_id,
            "evalSnapshot": {
                "id": eval_item.id,
                "name": eval_item.name,
                "inputs": eval_item.inputs,
                "evaluationCriterias": eval_item.evaluation_criterias,
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
        """Create payload for updating a coded eval run."""
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED
        return {
            "evalRunId": eval_run_id,
            "status": status.value,
            "result": {
                "output": dict(actual_output),
                "scores": evaluator_scores,  # Note: "scores" not "evaluatorScores"
            },
            "completionMetrics": {"duration": int(execution_time)},
            "evaluatorRuns": evaluator_runs,  # Note: "evaluatorRuns" not "assertionRuns"
        }

    def create_update_eval_set_run_payload(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        success: bool,
    ) -> dict[str, Any]:
        """Create payload for updating a coded eval set run."""
        scores_list = [
            {"value": avg_score, "evaluatorId": eval_id}
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
        evaluators: dict[str, BaseEvaluator[Any, Any, Any]],
        usage_metrics: dict[str, int | float | None],
        serialize_justification_fn: Callable[[Any], str | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results in coded evaluatorRuns format."""
        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        for eval_result in eval_results:
            if eval_result.evaluator_id not in evaluators:
                continue

            justification = serialize_justification_fn(eval_result.result.details)

            evaluator_scores_list.append(
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
                    "completionMetrics": {
                        "duration": int(eval_result.result.evaluation_time or 0),
                        "cost": usage_metrics["cost"],
                        "tokens": usage_metrics["tokens"] or 0,
                        "completionTokens": usage_metrics["completionTokens"] or 0,
                        "promptTokens": usage_metrics["promptTokens"] or 0,
                    },
                }
            )

        return evaluator_runs, evaluator_scores_list
