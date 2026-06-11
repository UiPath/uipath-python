"""Reporting strategy for the legacy (low-code) StudioWeb evaluation API."""

from typing import Any

from uipath.eval.evaluators import BaseLegacyEvaluator
from uipath.eval.models import EvalItemResult
from uipath.eval.models.evaluation_set import EvaluationItem

from ._models import EvaluationStatus
from ._utils import serialize_justification, to_deterministic_guid


class LegacyEvalReportingStrategy:
    """Legacy API: GUID identifiers, ``assertionRuns``, no ``coded/`` segment."""

    @property
    def endpoint_suffix(self) -> str:
        """Legacy endpoints have no extra path segment."""
        return ""

    def convert_id(self, id_value: str) -> str:
        """Legacy API expects GUIDs; map other strings to a deterministic uuid5."""
        return to_deterministic_guid(id_value)

    def build_eval_snapshot(self, eval_item: EvaluationItem) -> dict[str, Any]:
        """Legacy ``evalSnapshot`` carries ``expectedOutput`` at the root.

        Legacy evals are migrated to EvaluationItem format with expectedOutput
        inside evaluationCriterias; extract it from the first evaluator criteria
        (all criteria have the same expectedOutput).
        """
        expected_output = {}
        if eval_item.evaluation_criterias:
            first_criteria = next(iter(eval_item.evaluation_criterias.values()), None)
            if first_criteria and isinstance(first_criteria, dict):
                expected_output = first_criteria.get("expectedOutput", {})

        return {
            "id": self.convert_id(eval_item.id),
            "name": eval_item.name,
            "inputs": eval_item.inputs,
            "expectedOutput": expected_output,
        }

    @staticmethod
    def build_assertion_properties(
        evaluator: BaseLegacyEvaluator[Any],
    ) -> dict[str, Any]:
        """Build assertionProperties dict with prompt and model if available."""
        properties: dict[str, Any] = {}
        if hasattr(evaluator, "prompt") and isinstance(evaluator.prompt, str):
            properties["prompt"] = evaluator.prompt
        if hasattr(evaluator, "model") and isinstance(evaluator.model, str):
            properties["model"] = evaluator.model
        return properties

    def collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, Any],
        usage_metrics: dict[str, int | float | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect ``assertionRuns`` and scores with GUID evaluator IDs."""
        assertion_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        for eval_result in eval_results:
            # Skip results for evaluators not in the provided dict
            # (happens when processing mixed coded/legacy eval sets)
            if eval_result.evaluator_id not in evaluators:
                continue

            # Legacy API expects evaluatorId as GUID, convert string to GUID
            evaluator_id_value = self.convert_id(eval_result.evaluator_id)

            # Convert BaseModel justification to JSON string for API compatibility
            justification = serialize_justification(eval_result.result.details)

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
                        "duration": int(eval_result.result.evaluation_time * 1000)
                        if eval_result.result.evaluation_time
                        else 0,
                        "cost": usage_metrics["cost"],
                        "tokens": usage_metrics["tokens"] or 0,
                        "completionTokens": usage_metrics["completionTokens"] or 0,
                        "promptTokens": usage_metrics["promptTokens"] or 0,
                    },
                    "assertionSnapshot": {
                        "assertionType": evaluators[eval_result.evaluator_id].type.name,
                        "outputKey": evaluators[
                            eval_result.evaluator_id
                        ].target_output_key,
                        "assertionProperties": self.build_assertion_properties(
                            evaluators[eval_result.evaluator_id]
                        ),
                    },
                }
            )
        return assertion_runs, evaluator_scores_list

    def build_update_eval_run_payload(
        self,
        runs: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
        status: int,
    ) -> dict[str, Any]:
        """Legacy update payload: ``evaluatorScores`` + ``assertionRuns``."""
        return {
            "evalRunId": eval_run_id,
            # Backend expects integer status
            "status": status,
            "result": {
                "output": dict(actual_output),
                "evaluatorScores": scores,
            },
            "completionMetrics": {"duration": int(execution_time * 1000)},
            "assertionRuns": runs,
        }
