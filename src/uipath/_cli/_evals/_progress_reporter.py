"""Progress reporter for sending evaluation updates to StudioWeb."""

import functools
import json
import logging
import os
import uuid
from typing import Any, Dict, List
from urllib.parse import urlparse

from opentelemetry import trace
from pydantic import BaseModel
from rich.console import Console

from uipath import UiPath
from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._models._evaluator import Evaluator
from uipath._cli._evals._models._sw_reporting import (
    StudioWebAgentSnapshot,
    StudioWebProgressItem,
)
from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._project_files import (  # type: ignore
    get_project_config,
)
from uipath._events._event_bus import EventBus
from uipath._events._events import (
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunCreatedEvent,
    EvalSetRunUpdatedEvent,
    EvaluationEvents,
)
from uipath._utils import Endpoint, RequestSpec
from uipath._utils.constants import (
    ENV_EVAL_BACKEND_URL,
    ENV_TENANT_ID,
    HEADER_INTERNAL_TENANT_ID,
)
from uipath.eval.evaluators import (
    BaseEvaluator,
    LegacyBaseEvaluator,
)
from uipath.eval.models import EvalItemResult, ScoreType
from uipath.tracing import LlmOpsHttpExporter

logger = logging.getLogger(__name__)


def gracefully_handle_errors(func):
    """Decorator to catch and log errors without stopping execution."""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            if hasattr(self, "_console"):
                error_type = type(e).__name__
                logger.warning(
                    f"Cannot report progress to SW. "
                    f"Function: {func.__name__}, "
                    f"Error type: {error_type}, "
                    f"Details: {e}"
                )
            return None

    return wrapper


class StudioWebProgressReporter:
    """Handles reporting evaluation progress to StudioWeb."""

    def __init__(self, spans_exporter: LlmOpsHttpExporter):
        self.spans_exporter = spans_exporter

        logging.getLogger("uipath._cli.middlewares").setLevel(logging.CRITICAL)
        console_logger = ConsoleLogger.get_instance()

        # Use UIPATH_EVAL_BACKEND_URL for eval-specific routing if set
        eval_backend_url = os.getenv(ENV_EVAL_BACKEND_URL)
        uipath = UiPath(base_url=eval_backend_url) if eval_backend_url else UiPath()

        self._client = uipath.api_client
        self._console = console_logger
        self._rich_console = Console()
        self._project_id = os.getenv("UIPATH_PROJECT_ID", None)
        if not self._project_id:
            logger.warning(
                "Cannot report data to StudioWeb. Please set UIPATH_PROJECT_ID."
            )

        self.eval_set_run_ids: Dict[str, str] = {}
        self.evaluators: Dict[str, Any] = {}
        self.evaluator_scores: Dict[str, List[float]] = {}
        self.eval_run_ids: Dict[str, str] = {}
        self.is_coded_eval: Dict[str, bool] = {}  # Track coded vs legacy per execution
        self.eval_spans: Dict[
            str, list[Any]
        ] = {}  # Store spans per execution for usage metrics

    def _format_error_message(self, error: Exception, context: str) -> None:
        """Helper method to format and display error messages consistently."""
        self._rich_console.print(f"    • \u26a0  [dim]{context}: {error}[/dim]")

    def _is_localhost(self) -> bool:
        """Check if the eval backend URL is localhost.

        Returns:
            True if using localhost, False otherwise.
        """
        eval_backend_url = os.getenv(ENV_EVAL_BACKEND_URL, "")
        if eval_backend_url:
            try:
                parsed = urlparse(eval_backend_url)
                hostname = parsed.hostname or parsed.netloc.split(":")[0]
                return hostname.lower() in ("localhost", "127.0.0.1")
            except Exception:
                pass
        return False

    def _get_endpoint_prefix(self) -> str:
        """Determine the endpoint prefix based on environment.

        Checks UIPATH_EVAL_BACKEND_URL environment variable:
        - If set to localhost/127.0.0.1: returns "api/" (direct API access)
        - Otherwise: returns "agentsruntime_/api/" (service routing for alpha/prod)

        Returns:
            "api/" for localhost environments, "agentsruntime_/api/" for alpha/production.
        """
        if self._is_localhost():
            return "api/"
        return "agentsruntime_/api/"

    def _is_coded_evaluator(
        self, evaluators: List[BaseEvaluator[Any, Any, Any]]
    ) -> bool:
        """Check if evaluators are coded (BaseEvaluator) vs legacy (LegacyBaseEvaluator).

        Args:
            evaluators: List of evaluators to check

        Returns:
            True if using coded evaluators, False for legacy evaluators
        """
        if not evaluators:
            return False
        # Check the first evaluator type
        return not isinstance(evaluators[0], LegacyBaseEvaluator)

    def _extract_usage_from_spans(
        self, spans: list[Any]
    ) -> dict[str, int | float | None]:
        """Extract token usage and cost from OpenTelemetry spans.

        Args:
            spans: List of ReadableSpan objects from agent execution

        Returns:
            Dictionary with tokens, completionTokens, promptTokens, and cost
        """
        total_tokens = 0
        completion_tokens = 0
        prompt_tokens = 0
        total_cost = 0.0

        for span in spans:
            try:
                # Handle both dictionary attributes and string Attributes field
                attrs = None
                if hasattr(span, "attributes") and span.attributes:
                    if isinstance(span.attributes, dict):
                        attrs = span.attributes
                    elif isinstance(span.attributes, str):
                        # Parse JSON string attributes
                        attrs = json.loads(span.attributes)

                # Also check for Attributes field (capitalized) from backend spans
                if not attrs and hasattr(span, "Attributes") and span.Attributes:
                    if isinstance(span.Attributes, str):
                        attrs = json.loads(span.Attributes)
                    elif isinstance(span.Attributes, dict):
                        attrs = span.Attributes

                if attrs:
                    # Try to get usage from nested usage object (backend format)
                    if "usage" in attrs and isinstance(attrs["usage"], dict):
                        usage = attrs["usage"]
                        prompt_tokens += usage.get("promptTokens", 0)
                        completion_tokens += usage.get("completionTokens", 0)
                        total_tokens += usage.get("totalTokens", 0)
                        # Cost might be in usage or at root level
                        total_cost += usage.get("cost", 0.0)

                    # Also try OpenTelemetry semantic conventions (SDK format)
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

    @gracefully_handle_errors
    async def create_eval_set_run_sw(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        evaluators: List[LegacyBaseEvaluator[Any]],
        is_coded: bool = False,
    ) -> str:
        """Create a new evaluation set run in StudioWeb."""
        spec = self._create_eval_set_run_spec(
            eval_set_id, agent_snapshot, no_of_evals, is_coded
        )
        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )
        eval_set_run_id = json.loads(response.content)["id"]
        return eval_set_run_id

    @gracefully_handle_errors
    async def create_eval_run(
        self, eval_item: EvaluationItem, eval_set_run_id: str, is_coded: bool = False
    ) -> str:
        """Create a new evaluation run in StudioWeb.

        Args:
            eval_item: Dictionary containing evaluation data
            eval_set_run_id: The ID of the evaluation set run
            is_coded: Whether this is a coded evaluation (vs legacy)

        Returns:
            The ID of the created evaluation run
        """
        spec = self._create_eval_run_spec(eval_item, eval_set_run_id, is_coded)
        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )
        return json.loads(response.content)["id"]

    @gracefully_handle_errors
    async def update_eval_run(
        self,
        sw_progress_item: StudioWebProgressItem,
        evaluators: dict[str, Evaluator],
        is_coded: bool = False,
        spans: list[Any] | None = None,
    ):
        """Update an evaluation run with results."""
        coded_evaluators: dict[str, BaseEvaluator[Any, Any, Any]] = {}
        legacy_evaluators: dict[str, LegacyBaseEvaluator[Any]] = {}
        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores: list[dict[str, Any]] = []

        for k, v in evaluators.items():
            if isinstance(v, BaseEvaluator):
                coded_evaluators[k] = v
            elif isinstance(v, LegacyBaseEvaluator):
                legacy_evaluators[k] = v

        # Use coded evaluator format
        runs, scores = self._collect_coded_results(
            sw_progress_item.eval_results, coded_evaluators, spans or []
        )
        evaluator_runs.extend(runs)
        evaluator_scores.extend(scores)

        # Use legacy evaluator format
        runs, scores = self._collect_results(
            sw_progress_item.eval_results,
            legacy_evaluators,
            spans or [],
        )
        evaluator_runs.extend(runs)
        evaluator_scores.extend(scores)

        # Use the appropriate spec method based on evaluation type
        if is_coded:
            spec = self._update_coded_eval_run_spec(
                evaluator_runs=evaluator_runs,
                evaluator_scores=evaluator_scores,
                eval_run_id=sw_progress_item.eval_run_id,
                execution_time=sw_progress_item.agent_execution_time,
                actual_output=sw_progress_item.agent_output,
                is_coded=is_coded,
            )
        else:
            spec = self._update_eval_run_spec(
                assertion_runs=evaluator_runs,
                evaluator_scores=evaluator_scores,
                eval_run_id=sw_progress_item.eval_run_id,
                execution_time=sw_progress_item.agent_execution_time,
                actual_output=sw_progress_item.agent_output,
                is_coded=is_coded,
            )

        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

    @gracefully_handle_errors
    async def update_eval_set_run(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        is_coded: bool = False,
    ):
        """Update the evaluation set run status to complete."""
        spec = self._update_eval_set_run_spec(
            eval_set_run_id, evaluator_scores, is_coded
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

    async def handle_create_eval_set_run(self, payload: EvalSetRunCreatedEvent) -> None:
        try:
            self.evaluators = {eval.id: eval for eval in payload.evaluators}
            self.evaluator_scores = {eval.id: [] for eval in payload.evaluators}

            # Detect if using coded evaluators and store for this execution
            is_coded = self._is_coded_evaluator(payload.evaluators)
            self.is_coded_eval[payload.execution_id] = is_coded

            eval_set_run_id = payload.eval_set_run_id
            if not eval_set_run_id:
                eval_set_run_id = await self.create_eval_set_run_sw(
                    eval_set_id=payload.eval_set_id,
                    agent_snapshot=self._extract_agent_snapshot(payload.entrypoint),
                    no_of_evals=payload.no_of_evals,
                    evaluators=payload.evaluators,
                    is_coded=is_coded,
                )
            self.eval_set_run_ids[payload.execution_id] = eval_set_run_id
            current_span = trace.get_current_span()
            if current_span.is_recording():
                current_span.set_attribute("eval_set_run_id", eval_set_run_id)

            logger.debug(
                f"Created eval set run with ID: {eval_set_run_id} (coded={is_coded})"
            )

        except Exception as e:
            self._format_error_message(e, "StudioWeb create eval set run error")

    async def handle_create_eval_run(self, payload: EvalRunCreatedEvent) -> None:
        try:
            if eval_set_run_id := self.eval_set_run_ids.get(payload.execution_id):
                # Get the is_coded flag for this execution
                is_coded = self.is_coded_eval.get(payload.execution_id, False)
                eval_run_id = await self.create_eval_run(
                    payload.eval_item, eval_set_run_id, is_coded
                )
                if eval_run_id:
                    self.eval_run_ids[payload.execution_id] = eval_run_id
                    logger.debug(
                        f"Created eval run with ID: {eval_run_id} (coded={is_coded})"
                    )
            else:
                logger.warning("Cannot create eval run: eval_set_run_id not available")

        except Exception as e:
            self._format_error_message(e, "StudioWeb create eval run error")

    async def handle_update_eval_run(self, payload: EvalRunUpdatedEvent) -> None:
        try:
            self.spans_exporter.trace_id = self.eval_set_run_ids.get(
                payload.execution_id
            )

            self.spans_exporter.export(payload.spans)

            for eval_result in payload.eval_results:
                evaluator_id = eval_result.evaluator_id
                if evaluator_id in self.evaluator_scores:
                    match eval_result.result.score_type:
                        case ScoreType.NUMERICAL:
                            self.evaluator_scores[evaluator_id].append(
                                eval_result.result.score
                            )
                        case ScoreType.BOOLEAN:
                            self.evaluator_scores[evaluator_id].append(
                                100 if eval_result.result.score else 0
                            )
                        case ScoreType.ERROR:
                            self.evaluator_scores[evaluator_id].append(0)

            eval_run_id = self.eval_run_ids[payload.execution_id]
            if eval_run_id:
                # Get the is_coded flag for this execution
                is_coded = self.is_coded_eval.get(payload.execution_id, False)

                # Extract usage metrics from spans
                self._extract_usage_from_spans(payload.spans)

                await self.update_eval_run(
                    StudioWebProgressItem(
                        eval_run_id=eval_run_id,
                        eval_results=payload.eval_results,
                        success=payload.success,
                        agent_output=payload.agent_output,
                        agent_execution_time=payload.agent_execution_time,
                    ),
                    self.evaluators,
                    is_coded=is_coded,
                    spans=payload.spans,
                )

                logger.debug(
                    f"Updated eval run with ID: {eval_run_id} (coded={is_coded})"
                )

        except Exception as e:
            self._format_error_message(e, "StudioWeb reporting error")

    async def handle_update_eval_set_run(self, payload: EvalSetRunUpdatedEvent) -> None:
        try:
            if eval_set_run_id := self.eval_set_run_ids.get(payload.execution_id):
                # Get the is_coded flag for this execution
                is_coded = self.is_coded_eval.get(payload.execution_id, False)
                await self.update_eval_set_run(
                    eval_set_run_id,
                    payload.evaluator_scores,
                    is_coded=is_coded,
                )
                logger.debug(
                    f"Updated eval set run with ID: {eval_set_run_id} (coded={is_coded})"
                )
            else:
                logger.warning(
                    "Cannot update eval set run: eval_set_run_id not available"
                )

        except Exception as e:
            self._format_error_message(e, "StudioWeb update eval set run error")

    async def subscribe_to_eval_runtime_events(self, event_bus: EventBus) -> None:
        event_bus.subscribe(
            EvaluationEvents.CREATE_EVAL_SET_RUN, self.handle_create_eval_set_run
        )
        event_bus.subscribe(
            EvaluationEvents.CREATE_EVAL_RUN, self.handle_create_eval_run
        )
        event_bus.subscribe(
            EvaluationEvents.UPDATE_EVAL_RUN, self.handle_update_eval_run
        )
        event_bus.subscribe(
            EvaluationEvents.UPDATE_EVAL_SET_RUN, self.handle_update_eval_set_run
        )

        logger.debug("StudioWeb progress reporter subscribed to evaluation events")

    def _serialize_justification(
        self, justification: BaseModel | str | None
    ) -> str | None:
        """Serialize justification to JSON string for API compatibility.

        Args:
            justification: The justification object which could be None, a BaseModel,
                          a string, or any other JSON-serializable object

        Returns:
            JSON string representation or None if justification is None
        """
        if isinstance(justification, BaseModel):
            justification = json.dumps(justification.model_dump())

        return justification

    def _extract_agent_snapshot(self, entrypoint: str) -> StudioWebAgentSnapshot:
        try:
            project_config = get_project_config(os.getcwd())
            ep = None
            for entry_point in project_config.get("entryPoints", []):
                if entry_point.get("filePath") == entrypoint:
                    ep = entry_point
                    break

            if not ep:
                logger.warning(
                    f"Entrypoint {entrypoint} not found in configuration file"
                )
                return StudioWebAgentSnapshot(input_schema={}, output_schema={})

            input_schema = ep.get("input", {})
            output_schema = ep.get("output", {})

            return StudioWebAgentSnapshot(
                input_schema=input_schema, output_schema=output_schema
            )
        except Exception as e:
            logger.warning(f"Failed to extract agent snapshot: {e}")
            return StudioWebAgentSnapshot(input_schema={}, output_schema={})

    def _collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, LegacyBaseEvaluator[Any]],
        spans: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        assertion_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        # Extract usage metrics from spans
        usage_metrics = self._extract_usage_from_spans(spans)

        for eval_result in eval_results:
            # Skip results for evaluators not in the provided dict
            # (happens when processing mixed coded/legacy eval sets)
            if eval_result.evaluator_id not in evaluators:
                continue

            # Legacy API expects evaluatorId as GUID, convert string to GUID
            try:
                uuid.UUID(eval_result.evaluator_id)
                evaluator_id_value = eval_result.evaluator_id
            except ValueError:
                # Generate deterministic UUID5 from string
                evaluator_id_value = str(
                    uuid.uuid5(uuid.NAMESPACE_DNS, eval_result.evaluator_id)
                )

            # Convert BaseModel justification to JSON string for API compatibility
            justification = self._serialize_justification(eval_result.result.details)

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
                        "duration": int(eval_result.result.evaluation_time)
                        if eval_result.result.evaluation_time
                        else 0,
                        "cost": usage_metrics["cost"],
                        "tokens": usage_metrics["tokens"] or 0,
                        "completionTokens": usage_metrics["completionTokens"] or 0,
                        "promptTokens": usage_metrics["promptTokens"] or 0,
                    },
                    "assertionSnapshot": {
                        "assertionType": evaluators[
                            eval_result.evaluator_id
                        ].evaluator_type.name,
                        "outputKey": evaluators[
                            eval_result.evaluator_id
                        ].target_output_key,
                    },
                }
            )
        return assertion_runs, evaluator_scores_list

    def _collect_coded_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, BaseEvaluator[Any, Any, Any]],
        spans: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results for coded evaluators.

        Returns evaluatorRuns and scores in the format expected by coded eval endpoints.
        """
        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        # Extract usage metrics from spans
        usage_metrics = self._extract_usage_from_spans(spans)

        for eval_result in eval_results:
            # Skip results for evaluators not in the provided dict
            # (happens when processing mixed coded/legacy eval sets)
            if eval_result.evaluator_id not in evaluators:
                continue

            # Convert BaseModel justification to JSON string for API compatibility
            justification = self._serialize_justification(eval_result.result.details)

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
                        "duration": int(eval_result.result.evaluation_time)
                        if eval_result.result.evaluation_time
                        else 0,
                        "cost": usage_metrics["cost"],
                        "tokens": usage_metrics["tokens"] or 0,
                        "completionTokens": usage_metrics["completionTokens"] or 0,
                        "promptTokens": usage_metrics["promptTokens"] or 0,
                    },
                }
            )
        return evaluator_runs, evaluator_scores_list

    def _update_eval_run_spec(
        self,
        assertion_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
        is_coded: bool = False,
    ) -> RequestSpec:
        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalRun"
            ),
            json={
                "evalRunId": eval_run_id,
                "status": EvaluationStatus.COMPLETED.value,
                "result": {
                    "output": {**actual_output},
                    "evaluatorScores": evaluator_scores,
                },
                "completionMetrics": {"duration": int(execution_time)},
                "assertionRuns": assertion_runs,
            },
            headers=self._tenant_header(),
        )

    def _update_coded_eval_run_spec(
        self,
        evaluator_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
        is_coded: bool = False,
    ) -> RequestSpec:
        """Create update spec for coded evaluators."""
        # For coded evaluations, endpoint has /coded
        endpoint_suffix = "coded/" if is_coded else ""
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalRun"
            ),
            json={
                "evalRunId": eval_run_id,
                "status": EvaluationStatus.COMPLETED.value,
                "result": {
                    "output": {**actual_output},
                    "scores": evaluator_scores,
                },
                "completionMetrics": {"duration": int(execution_time)},
                "evaluatorRuns": evaluator_runs,
            },
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(
        self, eval_item: EvaluationItem, eval_set_run_id: str, is_coded: bool = False
    ) -> RequestSpec:
        # Legacy API expects eval IDs as GUIDs, coded accepts strings
        # Convert string IDs to deterministic GUIDs for legacy
        if is_coded:
            eval_item_id = eval_item.id
        else:
            # Try to parse as GUID, if it fails, generate deterministic GUID from string
            try:
                uuid.UUID(eval_item.id)
                eval_item_id = eval_item.id
            except ValueError:
                # Generate deterministic UUID5 from string
                eval_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, eval_item.id))

        # Build eval snapshot based on evaluation item type
        eval_snapshot = {
            "id": eval_item_id,
            "name": eval_item.name,
            "inputs": eval_item.inputs,
        }

        # For new coded evaluators (EvaluationItem), use evaluationCriterias
        # For legacy evaluators (LegacyEvaluationItem), use expectedOutput
        if isinstance(eval_item, EvaluationItem):
            eval_snapshot["evaluationCriterias"] = eval_item.evaluation_criterias
        else:
            eval_snapshot["expectedOutput"] = eval_item.expected_output

        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalRun"
            ),
            json={
                "evalSetRunId": eval_set_run_id,
                "evalSnapshot": eval_snapshot,
                "status": EvaluationStatus.IN_PROGRESS.value,
            },
            headers=self._tenant_header(),
        )

    def _create_eval_set_run_spec(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        is_coded: bool = False,
    ) -> RequestSpec:
        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""

        # Legacy API expects evalSetId as GUID, coded accepts string
        # Convert string IDs to deterministic GUIDs for legacy
        if is_coded:
            eval_set_id_value = eval_set_id
        else:
            # Try to parse as GUID, if it fails, generate deterministic GUID from string
            try:
                uuid.UUID(eval_set_id)
                eval_set_id_value = eval_set_id
            except ValueError:
                # Generate deterministic UUID5 from string
                eval_set_id_value = str(uuid.uuid5(uuid.NAMESPACE_DNS, eval_set_id))

        payload = {
            "agentId": self._project_id,
            "evalSetId": eval_set_id_value,
            "agentSnapshot": agent_snapshot.model_dump(by_alias=True),
            "status": EvaluationStatus.IN_PROGRESS.value,
            "numberOfEvalsExecuted": no_of_evals,
        }

        # Add version field for coded evaluations
        if is_coded:
            payload["version"] = "1.0"

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalSetRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _update_eval_set_run_spec(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        is_coded: bool = False,
    ) -> RequestSpec:
        # Legacy API expects evaluatorId as GUID, coded accepts string
        evaluator_scores_list = []
        for evaluator_id, avg_score in evaluator_scores.items():
            if is_coded:
                evaluator_id_value = evaluator_id
            else:
                # Convert string to GUID for legacy
                try:
                    uuid.UUID(evaluator_id)
                    evaluator_id_value = evaluator_id
                except ValueError:
                    # Generate deterministic UUID5 from string
                    evaluator_id_value = str(
                        uuid.uuid5(uuid.NAMESPACE_DNS, evaluator_id)
                    )

            evaluator_scores_list.append(
                {"value": avg_score, "evaluatorId": evaluator_id_value}
            )

        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalSetRun"
            ),
            json={
                "evalSetRunId": eval_set_run_id,
                "status": EvaluationStatus.COMPLETED.value,
                "evaluatorScores": evaluator_scores_list,
            },
            headers=self._tenant_header(),
        )

    def _tenant_header(self) -> dict[str, str]:
        tenant_id = os.getenv(ENV_TENANT_ID, None)
        if not tenant_id:
            self._console.error(
                f"{ENV_TENANT_ID} env var is not set. Please run 'uipath auth'."
            )
        return {HEADER_INTERNAL_TENANT_ID: tenant_id}  # type: ignore
