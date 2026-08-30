"""Base payload builder with shared utilities for evaluation reporting."""

import json
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot
from uipath._utils import Endpoint, RequestSpec
from uipath.eval.models import EvalItemResult

logger = logging.getLogger(__name__)


class BasePayloadBuilder(ABC):
    """Abstract base class for payload builders.

    Provides shared utilities for both coded and legacy payload building.
    """

    def __init__(
        self,
        project_id: str | None,
        endpoint_prefix: str,
        tenant_header: dict[str, str | None],
    ):
        self._project_id = project_id
        self._endpoint_prefix = endpoint_prefix
        self._tenant_header = tenant_header

    @property
    @abstractmethod
    def endpoint_suffix(self) -> str:
        """Return the endpoint suffix for this builder type.

        Returns:
            "coded/" for coded evaluations, "" for legacy.
        """
        pass

    @abstractmethod
    def format_id(self, id_value: str) -> str:
        """Format an ID for the backend API.

        Args:
            id_value: The ID to format.

        Returns:
            Formatted ID (GUID for legacy, string for coded).
        """
        pass

    @abstractmethod
    def build_eval_snapshot(self, eval_item: EvaluationItem) -> dict[str, Any]:
        """Build the eval snapshot portion of the payload.

        Args:
            eval_item: The evaluation item.

        Returns:
            Dict containing the eval snapshot.
        """
        pass

    @abstractmethod
    def collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, Any],
        usage_metrics: dict[str, int | float | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect and format evaluation results.

        Args:
            eval_results: List of evaluation results.
            evaluators: Dict of evaluator ID to evaluator instance.
            usage_metrics: Token usage and cost metrics.

        Returns:
            Tuple of (runs_list, scores_list).
        """
        pass

    @abstractmethod
    def build_update_eval_run_payload(
        self,
        eval_run_id: str,
        runs: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
    ) -> dict[str, Any]:
        """Build the payload for updating an eval run.

        Args:
            eval_run_id: The evaluation run ID.
            runs: List of evaluator/assertion runs.
            scores: List of evaluator scores.
            actual_output: The agent's actual output.
            execution_time: Total execution time.
            success: Whether the evaluation succeeded.

        Returns:
            The payload dict.
        """
        pass

    # Shared utility methods

    @staticmethod
    def string_to_deterministic_guid(value: str) -> str:
        """Convert a string to a deterministic GUID using UUID5.

        Args:
            value: The string to convert.

        Returns:
            A deterministic GUID string.
        """
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, value))

    @staticmethod
    def try_parse_or_convert_guid(value: str) -> str:
        """Try to parse as GUID, or convert string to deterministic GUID.

        Args:
            value: The string to parse or convert.

        Returns:
            A valid GUID string.
        """
        try:
            uuid.UUID(value)
            return value
        except ValueError:
            return BasePayloadBuilder.string_to_deterministic_guid(value)

    @staticmethod
    def serialize_justification(justification: BaseModel | str | None) -> str | None:
        """Serialize justification to JSON string for API compatibility.

        Args:
            justification: The justification object.

        Returns:
            JSON string representation or None.
        """
        if isinstance(justification, BaseModel):
            return json.dumps(justification.model_dump())
        return justification

    @staticmethod
    def extract_usage_from_spans(spans: list[Any]) -> dict[str, int | float | None]:
        """Extract token usage and cost from OpenTelemetry spans.

        Args:
            spans: List of ReadableSpan objects from agent execution.

        Returns:
            Dictionary with tokens, completionTokens, promptTokens, and cost.
        """
        total_tokens = 0
        completion_tokens = 0
        prompt_tokens = 0
        total_cost = 0.0

        for span in spans:
            try:
                attrs = None
                if hasattr(span, "attributes") and span.attributes:
                    if isinstance(span.attributes, dict):
                        attrs = span.attributes
                    elif isinstance(span.attributes, str):
                        attrs = json.loads(span.attributes)

                if not attrs and hasattr(span, "Attributes") and span.Attributes:
                    if isinstance(span.Attributes, str):
                        attrs = json.loads(span.Attributes)
                    elif isinstance(span.Attributes, dict):
                        attrs = span.Attributes

                if attrs:
                    if "usage" in attrs and isinstance(attrs["usage"], dict):
                        usage = attrs["usage"]
                        prompt_tokens += usage.get("promptTokens", 0)
                        completion_tokens += usage.get("completionTokens", 0)
                        total_tokens += usage.get("totalTokens", 0)
                        total_cost += usage.get("cost", 0.0)

                    prompt_tokens += attrs.get("gen_ai.usage.prompt_tokens", 0)
                    completion_tokens += attrs.get("gen_ai.usage.completion_tokens", 0)
                    total_tokens += attrs.get("gen_ai.usage.total_tokens", 0)
                    total_cost += attrs.get("gen_ai.usage.cost", 0.0)
                    total_cost += attrs.get("llm.usage.cost", 0.0)

            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                logger.debug(f"Failed to parse span attributes: {e}")
                continue

        return {
            "tokens": total_tokens if total_tokens > 0 else None,
            "completionTokens": completion_tokens if completion_tokens > 0 else None,
            "promptTokens": prompt_tokens if prompt_tokens > 0 else None,
            "cost": total_cost if total_cost > 0 else None,
        }

    @staticmethod
    def build_completion_metrics(
        duration: float | None,
        usage_metrics: dict[str, int | float | None],
    ) -> dict[str, Any]:
        """Build completion metrics dict.

        Args:
            duration: Execution duration in seconds.
            usage_metrics: Token usage and cost metrics.

        Returns:
            Completion metrics dict.
        """
        return {
            "duration": int(duration) if duration else 0,
            "cost": usage_metrics["cost"],
            "tokens": usage_metrics["tokens"] or 0,
            "completionTokens": usage_metrics["completionTokens"] or 0,
            "promptTokens": usage_metrics["promptTokens"] or 0,
        }

    # Request spec builders (shared structure, use abstract methods for differences)

    def build_create_eval_set_run_spec(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
    ) -> RequestSpec:
        """Build request spec for creating an eval set run.

        Args:
            eval_set_id: The evaluation set ID.
            agent_snapshot: The agent snapshot.
            no_of_evals: Number of evaluations.

        Returns:
            RequestSpec for the API call.
        """
        payload = {
            "agentId": self._project_id,
            "evalSetId": self.format_id(eval_set_id),
            "agentSnapshot": agent_snapshot.model_dump(by_alias=True),
            "status": EvaluationStatus.IN_PROGRESS.value,
            "numberOfEvalsExecuted": no_of_evals,
            "source": 0,
        }

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._endpoint_prefix}execution/agents/{self._project_id}/{self.endpoint_suffix}evalSetRun"
            ),
            json=payload,
            headers=self._tenant_header,
        )

    def build_create_eval_run_spec(
        self,
        eval_item: EvaluationItem,
        eval_set_run_id: str,
    ) -> RequestSpec:
        """Build request spec for creating an eval run.

        Args:
            eval_item: The evaluation item.
            eval_set_run_id: The eval set run ID.

        Returns:
            RequestSpec for the API call.
        """
        eval_snapshot = self.build_eval_snapshot(eval_item)

        payload = {
            "evalSetRunId": eval_set_run_id,
            "evalSnapshot": eval_snapshot,
            "status": EvaluationStatus.IN_PROGRESS.value,
        }

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._endpoint_prefix}execution/agents/{self._project_id}/{self.endpoint_suffix}evalRun"
            ),
            json=payload,
            headers=self._tenant_header,
        )

    def build_update_eval_run_spec(
        self,
        eval_run_id: str,
        runs: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
    ) -> RequestSpec:
        """Build request spec for updating an eval run.

        Args:
            eval_run_id: The evaluation run ID.
            runs: List of evaluator/assertion runs.
            scores: List of evaluator scores.
            actual_output: The agent's actual output.
            execution_time: Total execution time.
            success: Whether the evaluation succeeded.

        Returns:
            RequestSpec for the API call.
        """
        payload = self.build_update_eval_run_payload(
            eval_run_id, runs, scores, actual_output, execution_time, success
        )

        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._endpoint_prefix}execution/agents/{self._project_id}/{self.endpoint_suffix}evalRun"
            ),
            json=payload,
            headers=self._tenant_header,
        )

    def build_update_eval_set_run_spec(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        success: bool = True,
    ) -> RequestSpec:
        """Build request spec for updating an eval set run.

        Args:
            eval_set_run_id: The eval set run ID.
            evaluator_scores: Dict of evaluator ID to average score.
            success: Whether the evaluation set succeeded.

        Returns:
            RequestSpec for the API call.
        """
        scores_list = [
            {"value": avg_score, "evaluatorId": self.format_id(evaluator_id)}
            for evaluator_id, avg_score in evaluator_scores.items()
        ]

        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED

        payload = {
            "evalSetRunId": eval_set_run_id,
            "status": status.value,
            "evaluatorScores": scores_list,
        }

        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._endpoint_prefix}execution/agents/{self._project_id}/{self.endpoint_suffix}evalSetRun"
            ),
            json=payload,
            headers=self._tenant_header,
        )
