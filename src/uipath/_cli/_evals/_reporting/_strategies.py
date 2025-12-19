"""Evaluation reporting strategies for legacy and coded evaluations.

This module defines the Strategy Pattern for handling the differences between
legacy and coded evaluation API formats, including ID conversion, endpoint
routing, and payload structure.
"""

import uuid
from typing import Any, Callable, Protocol, runtime_checkable

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot
from uipath.eval.evaluators import BaseEvaluator, LegacyBaseEvaluator

# =============================================================================
# Strategy Protocol
# =============================================================================


@runtime_checkable
class EvalReportingStrategy(Protocol):
    """Protocol for evaluation reporting strategies.

    Strategies handle the differences between legacy and coded evaluation
    API formats, including ID conversion, endpoint routing, and payload structure.
    """

    @property
    def endpoint_suffix(self) -> str:
        """Return the endpoint suffix for this strategy.

        Returns:
            "" for legacy, "coded/" for coded evaluations
        """
        ...

    def convert_id(self, id_value: str) -> str:
        """Convert an ID to the format expected by the backend.

        Args:
            id_value: The original string ID

        Returns:
            For legacy: deterministic GUID from uuid5
            For coded: original string ID unchanged
        """
        ...

    def create_eval_set_run_payload(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        project_id: str,
    ) -> dict[str, Any]:
        """Create the payload for creating an eval set run."""
        ...

    def create_eval_run_payload(
        self,
        eval_item: EvaluationItem,
        eval_set_run_id: str,
    ) -> dict[str, Any]:
        """Create the payload for creating an eval run."""
        ...

    def create_update_eval_run_payload(
        self,
        eval_run_id: str,
        evaluator_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
    ) -> dict[str, Any]:
        """Create the payload for updating an eval run."""
        ...

    def create_update_eval_set_run_payload(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        success: bool,
    ) -> dict[str, Any]:
        """Create the payload for updating an eval set run."""
        ...

    def collect_results(
        self,
        eval_results: list[Any],
        evaluators: dict[str, Any],
        usage_metrics: dict[str, int | float | None],
        serialize_justification_fn: Callable[[Any], str | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results from evaluations in strategy-specific format.

        Returns:
            Tuple of (evaluator_runs, evaluator_scores)
        """
        ...


# =============================================================================
# Legacy Evaluation Reporting Strategy
# =============================================================================


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


# =============================================================================
# Coded Evaluation Reporting Strategy
# =============================================================================


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
