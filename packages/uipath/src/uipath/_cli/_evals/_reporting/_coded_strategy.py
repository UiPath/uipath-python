"""Reporting strategy for the coded StudioWeb evaluation API."""

from typing import Any

from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import EvalItemResult
from uipath.eval.models.evaluation_set import EvaluationItem

from ._models import EvaluationStatus
from ._utils import serialize_justification


class CodedEvalReportingStrategy:
    """Coded API: string identifiers, ``evaluatorRuns``, ``coded/`` segment."""

    @property
    def endpoint_suffix(self) -> str:
        """Coded endpoints live under the ``coded/`` path segment."""
        return "coded/"

    def convert_id(self, id_value: str) -> str:
        """The coded API accepts arbitrary string IDs unchanged."""
        return id_value

    def build_eval_snapshot(self, eval_item: EvaluationItem) -> dict[str, Any]:
        """Coded ``evalSnapshot`` carries ``evaluationCriterias`` directly."""
        return {
            "id": self.convert_id(eval_item.id),
            "name": eval_item.name,
            "inputs": eval_item.inputs,
            "evaluationCriterias": eval_item.evaluation_criterias,
        }

    @staticmethod
    def build_evaluator_snapshot(
        evaluator: BaseEvaluator[Any, Any, Any],
    ) -> dict[str, Any]:
        """Build evaluatorSnapshot dict with prompt and model if available."""
        snapshot: dict[str, Any] = {}
        config = getattr(evaluator, "evaluator_config", None)
        if config is not None:
            if hasattr(config, "prompt") and isinstance(config.prompt, str):
                snapshot["prompt"] = config.prompt
            if hasattr(config, "model") and isinstance(config.model, str):
                snapshot["model"] = config.model
        return snapshot

    def collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, Any],
        usage_metrics: dict[str, int | float | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect ``evaluatorRuns`` and scores with string evaluator IDs."""
        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        for eval_result in eval_results:
            # Skip results for evaluators not in the provided dict
            # (happens when processing mixed coded/legacy eval sets)
            if eval_result.evaluator_id not in evaluators:
                continue

            # Convert BaseModel justification to JSON string for API compatibility
            justification = serialize_justification(eval_result.result.details)

            evaluator_scores_list.append(
                {
                    "type": eval_result.result.score_type.value,
                    "value": eval_result.result.score,
                    "justification": justification,
                    "evaluatorId": eval_result.evaluator_id,
                }
            )
            evaluator_run: dict[str, Any] = {
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
                    "duration": int(eval_result.result.evaluation_time * 1000)
                    if eval_result.result.evaluation_time
                    else 0,
                    "cost": usage_metrics["cost"],
                    "tokens": usage_metrics["tokens"] or 0,
                    "completionTokens": usage_metrics["completionTokens"] or 0,
                    "promptTokens": usage_metrics["promptTokens"] or 0,
                },
            }
            snapshot = self.build_evaluator_snapshot(
                evaluators[eval_result.evaluator_id]
            )
            if snapshot:
                evaluator_run["evaluatorSnapshot"] = snapshot
            evaluator_runs.append(evaluator_run)
        return evaluator_runs, evaluator_scores_list

    def build_update_eval_run_payload(
        self,
        runs: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
        status: int,
    ) -> dict[str, Any]:
        """Coded update payload: ``scores`` + ``evaluatorRuns``."""
        return {
            "evalRunId": eval_run_id,
            "status": status,
            "result": {
                "output": dict(actual_output),
                "scores": scores,
            },
            "completionMetrics": {"duration": int(execution_time * 1000)},
            "evaluatorRuns": runs,
        }
