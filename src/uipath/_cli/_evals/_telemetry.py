"""Telemetry subscriber for sending evaluation events to Application Insights.

This subscriber listens to evaluation lifecycle events and sends custom telemetry
events to Application Insights for monitoring and analytics.
"""

import logging
import os
import time
from typing import Any

from uipath._cli._utils._common import get_claim_from_token
from uipath._events._event_bus import EventBus
from uipath.eval.runtime.events import (
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunCreatedEvent,
    EvalSetRunUpdatedEvent,
    EvaluationEvents,
)
from uipath.platform.common._config import UiPathConfig
from uipath.telemetry._track import is_telemetry_enabled, track_event

logger = logging.getLogger(__name__)

# Telemetry event names for Application Insights
EVAL_SET_RUN_STARTED = "EvalSetRun.Start"
EVAL_SET_RUN_COMPLETED = "EvalSetRun.End"
EVAL_SET_RUN_FAILED = "EvalSetRun.Failed"
EVAL_RUN_STARTED = "EvalRun.Start"
EVAL_RUN_COMPLETED = "EvalRun.End"
EVAL_RUN_FAILED = "EvalRun.Failed"


class EvalTelemetrySubscriber:
    """Subscribes to evaluation events and sends telemetry to Application Insights.

    This subscriber listens to the evaluation event bus and tracks:
    - Eval set run start/complete/fail events
    - Eval run start/complete/fail events

    Telemetry is sent asynchronously and failures are silently ignored to ensure
    evaluation execution is never blocked by telemetry issues.

    Usage:
        event_bus = EventBus()
        telemetry_subscriber = EvalTelemetrySubscriber()
        await telemetry_subscriber.subscribe_to_eval_runtime_events(event_bus)
    """

    def __init__(self) -> None:
        """Initialize the telemetry subscriber."""
        self._eval_set_start_times: dict[str, float] = {}
        self._eval_run_start_times: dict[str, float] = {}
        self._eval_set_info: dict[str, dict[str, Any]] = {}
        self._eval_run_info: dict[str, dict[str, Any]] = {}
        self._current_eval_set_run_id: str | None = None
        self._current_entrypoint: str | None = None

    @staticmethod
    def _get_agent_type(entrypoint: str) -> str:
        """Determine agent type from entrypoint.

        Args:
            entrypoint: The entrypoint path.

        Returns:
            "LowCode" if entrypoint is "agent.json", "Coded" otherwise.
        """
        if entrypoint == "agent.json":
            return "LowCode"
        return "Coded"

    async def subscribe_to_eval_runtime_events(self, event_bus: EventBus) -> None:
        """Subscribe to evaluation runtime events.

        Args:
            event_bus: The event bus to subscribe to.
        """
        if not is_telemetry_enabled():
            return

        event_bus.subscribe(
            EvaluationEvents.CREATE_EVAL_SET_RUN, self._on_eval_set_run_created
        )
        event_bus.subscribe(EvaluationEvents.CREATE_EVAL_RUN, self._on_eval_run_created)
        event_bus.subscribe(EvaluationEvents.UPDATE_EVAL_RUN, self._on_eval_run_updated)
        event_bus.subscribe(
            EvaluationEvents.UPDATE_EVAL_SET_RUN, self._on_eval_set_run_updated
        )

    async def _on_eval_set_run_created(self, event: EvalSetRunCreatedEvent) -> None:
        """Handle eval set run created event.

        Args:
            event: The eval set run created event.
        """
        try:
            self._eval_set_start_times[event.execution_id] = time.time()

            eval_set_run_id = event.eval_set_run_id or event.execution_id

            self._eval_set_info[event.execution_id] = {
                "eval_set_id": event.eval_set_id,
                "eval_set_run_id": eval_set_run_id,
                "entrypoint": event.entrypoint,
                "no_of_evals": event.no_of_evals,
                "evaluator_count": len(event.evaluators),
            }

            # Store for child events
            self._current_eval_set_run_id = eval_set_run_id
            self._current_entrypoint = event.entrypoint

            properties: dict[str, Any] = {
                "EvalSetId": event.eval_set_id,
                "EvalSetRunId": eval_set_run_id,
                "Entrypoint": event.entrypoint,
                "EvalCount": event.no_of_evals,
                "EvaluatorCount": len(event.evaluators),
                "AgentType": self._get_agent_type(event.entrypoint),
                "Runtime": "URT",
            }

            self._enrich_properties(properties)

            track_event(EVAL_SET_RUN_STARTED, properties)

        except Exception as e:
            logger.debug(f"Error tracking eval set run started: {e}")

    async def _on_eval_run_created(self, event: EvalRunCreatedEvent) -> None:
        """Handle eval run created event.

        Args:
            event: The eval run created event.
        """
        try:
            self._eval_run_start_times[event.execution_id] = time.time()
            self._eval_run_info[event.execution_id] = {
                "eval_item_id": event.eval_item.id,
                "eval_item_name": event.eval_item.name,
            }

            properties: dict[str, Any] = {
                "EvalId": event.eval_item.id,
                "EvalName": event.eval_item.name,
                "Runtime": "URT",
            }

            # Add eval set run id from parent
            if self._current_eval_set_run_id:
                properties["EvalSetRunId"] = self._current_eval_set_run_id

            # Add entrypoint and agent type
            if self._current_entrypoint:
                properties["Entrypoint"] = self._current_entrypoint
                properties["AgentType"] = self._get_agent_type(self._current_entrypoint)

            self._enrich_properties(properties)

            track_event(EVAL_RUN_STARTED, properties)

        except Exception as e:
            logger.debug(f"Error tracking eval run started: {e}")

    async def _on_eval_run_updated(self, event: EvalRunUpdatedEvent) -> None:
        """Handle eval run updated (completed/failed) event.

        Args:
            event: The eval run updated event.
        """
        try:
            # Calculate duration
            start_time = self._eval_run_start_times.pop(event.execution_id, None)
            duration_ms = int((time.time() - start_time) * 1000) if start_time else None

            # Get stored info
            run_info = self._eval_run_info.pop(event.execution_id, {})

            # Calculate average score
            scores = [
                r.result.score for r in event.eval_results if r.result.score is not None
            ]
            avg_score = sum(scores) / len(scores) if scores else None

            # Try to get trace ID from spans
            trace_id: str | None = None
            if event.spans:
                for span in event.spans:
                    if span.context and span.context.trace_id:
                        # Format trace ID as hex string
                        trace_id = format(span.context.trace_id, "032x")
                        break

            properties: dict[str, Any] = {
                "EvalId": run_info.get("eval_item_id", event.eval_item.id),
                "EvalName": run_info.get("eval_item_name", event.eval_item.name),
                "Success": event.success,
                "EvaluatorCount": len(event.eval_results),
                "Runtime": "URT",
            }

            if self._current_eval_set_run_id:
                properties["EvalSetRunId"] = self._current_eval_set_run_id

            if self._current_entrypoint:
                properties["Entrypoint"] = self._current_entrypoint
                properties["AgentType"] = self._get_agent_type(self._current_entrypoint)

            if trace_id:
                properties["TraceId"] = trace_id

            if duration_ms is not None:
                properties["DurationMs"] = duration_ms

            if avg_score is not None:
                properties["AverageScore"] = avg_score

            if event.agent_execution_time:
                properties["AgentExecutionTimeMs"] = int(
                    event.agent_execution_time * 1000
                )

            if event.exception_details:
                properties["ErrorType"] = type(
                    event.exception_details.exception
                ).__name__
                properties["ErrorMessage"] = str(event.exception_details.exception)[
                    :500
                ]
                properties["IsRuntimeException"] = (
                    event.exception_details.runtime_exception
                )

            self._enrich_properties(properties)

            event_name = EVAL_RUN_COMPLETED if event.success else EVAL_RUN_FAILED
            track_event(event_name, properties)

        except Exception as e:
            logger.debug(f"Error tracking eval run updated: {e}")

    async def _on_eval_set_run_updated(self, event: EvalSetRunUpdatedEvent) -> None:
        """Handle eval set run updated (completed/failed) event.

        Args:
            event: The eval set run updated event.
        """
        try:
            # Calculate duration
            start_time = self._eval_set_start_times.pop(event.execution_id, None)
            duration_ms = int((time.time() - start_time) * 1000) if start_time else None

            # Get stored info
            set_info = self._eval_set_info.pop(event.execution_id, {})

            # Calculate overall average score
            scores = list(event.evaluator_scores.values())
            avg_score = sum(scores) / len(scores) if scores else None

            properties: dict[str, Any] = {
                "EvalSetId": set_info.get("eval_set_id", "unknown"),
                "Success": event.success,
                "EvaluatorCount": len(event.evaluator_scores),
            }

            if set_info.get("eval_set_run_id"):
                properties["EvalSetRunId"] = set_info["eval_set_run_id"]

            if set_info.get("entrypoint"):
                properties["Entrypoint"] = set_info["entrypoint"]
                properties["AgentType"] = self._get_agent_type(set_info["entrypoint"])

            properties["Runtime"] = "URT"

            if set_info.get("no_of_evals"):
                properties["EvalCount"] = set_info["no_of_evals"]

            if duration_ms is not None:
                properties["DurationMs"] = duration_ms

            if avg_score is not None:
                properties["AverageScore"] = avg_score

            # Add individual evaluator scores
            for evaluator_id, score in event.evaluator_scores.items():
                # Sanitize evaluator ID for use as property key
                safe_key = f"Score_{evaluator_id.replace('-', '_')[:50]}"
                properties[safe_key] = score

            self._enrich_properties(properties)

            event_name = (
                EVAL_SET_RUN_COMPLETED if event.success else EVAL_SET_RUN_FAILED
            )
            track_event(event_name, properties)

            self._current_eval_set_run_id = None
            self._current_entrypoint = None

        except Exception as e:
            logger.debug(f"Error tracking eval set run updated: {e}")

    def _enrich_properties(self, properties: dict[str, Any]) -> None:
        """Enrich properties with common context information.

        Args:
            properties: The properties dictionary to enrich.
        """
        # Add UiPath context
        if UiPathConfig.project_id:
            properties["ProjectId"] = UiPathConfig.project_id
            properties["AgentId"] = UiPathConfig.project_id

        # Get organization ID from UiPathConfig
        if UiPathConfig.organization_id:
            properties["CloudOrganizationId"] = UiPathConfig.organization_id

        # Get CloudUserId from JWT token
        try:
            cloud_user_id = get_claim_from_token("sub")
            if cloud_user_id:
                properties["CloudUserId"] = cloud_user_id
        except Exception:
            pass  # CloudUserId is optional

        # Get tenant ID from environment
        tenant_id = os.getenv("UIPATH_TENANT_ID")
        if tenant_id:
            properties["TenantId"] = tenant_id

        # Add source identifier
        properties["Source"] = "uipath-python-cli"
        properties["ApplicationName"] = "UiPath.Eval"
