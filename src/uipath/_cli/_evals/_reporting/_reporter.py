"""StudioWeb Progress Reporter for evaluation runs.

This module provides the main reporter class for sending evaluation
progress updates to StudioWeb, including creating and updating
eval set runs and individual eval runs.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.trace import SpanContext, SpanKind, TraceFlags
from pydantic import BaseModel
from rich.console import Console

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
)
from uipath._cli._evals._models._evaluator import Evaluator
from uipath._cli._evals._models._sw_reporting import (
    StudioWebAgentSnapshot,
    StudioWebProgressItem,
)
from uipath._cli._evals._reporting._strategies import (
    CodedEvalReportingStrategy,
    EvalReportingStrategy,
    LegacyEvalReportingStrategy,
)
from uipath._cli._evals._reporting._utils import gracefully_handle_errors
from uipath._cli._utils._console import ConsoleLogger
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
from uipath.platform import UiPath
from uipath.platform.common import UiPathConfig
from uipath.tracing import LlmOpsHttpExporter

logger = logging.getLogger(__name__)


class StudioWebProgressReporter:
    """Handles reporting evaluation progress to StudioWeb.

    Uses the Strategy Pattern to delegate legacy vs coded evaluation
    formatting to appropriate strategy classes.
    """

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

        # Strategy instances
        self._legacy_strategy = LegacyEvalReportingStrategy()
        self._coded_strategy = CodedEvalReportingStrategy()

        # State tracking
        self.eval_set_run_ids: dict[str, str] = {}
        self.evaluators: dict[str, Any] = {}
        self.evaluator_scores: dict[str, list[float]] = {}
        self.eval_run_ids: dict[str, str] = {}
        self.is_coded_eval: dict[str, bool] = {}
        self.eval_spans: dict[str, list[Any]] = {}
        self.eval_set_execution_id: str | None = None

    # -------------------------------------------------------------------------
    # Strategy Selection
    # -------------------------------------------------------------------------

    def _get_strategy(self, is_coded: bool) -> EvalReportingStrategy:
        """Get the appropriate strategy for the evaluation type."""
        return self._coded_strategy if is_coded else self._legacy_strategy

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _format_error_message(self, error: Exception, context: str) -> None:
        """Helper method to format and display error messages consistently."""
        self._rich_console.print(f"    • \u26a0  [dim]{context}: {error}[/dim]")

    def _is_localhost(self) -> bool:
        """Check if the eval backend URL is localhost."""
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
        """Determine the endpoint prefix based on environment."""
        if self._is_localhost():
            return "api/"
        return "agentsruntime_/api/"

    def _is_coded_evaluator(
        self, evaluators: list[BaseEvaluator[Any, Any, Any]]
    ) -> bool:
        """Check if evaluators are coded (BaseEvaluator) vs legacy (LegacyBaseEvaluator)."""
        if not evaluators:
            return False
        return not isinstance(evaluators[0], LegacyBaseEvaluator)

    def _serialize_justification(
        self, justification: BaseModel | str | None
    ) -> str | None:
        """Serialize justification to JSON string for API compatibility."""
        if isinstance(justification, BaseModel):
            justification = json.dumps(justification.model_dump())
        return justification

    def _tenant_header(self) -> dict[str, str | None]:
        """Build tenant header for API requests."""
        tenant_id = os.getenv(ENV_TENANT_ID, None)
        if not tenant_id:
            self._console.error(
                f"{ENV_TENANT_ID} env var is not set. Please run 'uipath auth'."
            )
        return {HEADER_INTERNAL_TENANT_ID: tenant_id}

    def _extract_usage_from_spans(
        self, spans: list[Any]
    ) -> dict[str, int | float | None]:
        """Extract token usage and cost from OpenTelemetry spans."""
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

    def _extract_agent_snapshot(self, entrypoint: str) -> StudioWebAgentSnapshot:
        """Extract agent snapshot from entry points configuration."""
        try:
            entry_points_file_path = os.path.join(
                os.getcwd(), str(UiPathConfig.entry_points_file_path)
            )
            if not os.path.exists(entry_points_file_path):
                return StudioWebAgentSnapshot(input_schema={}, output_schema={})

            with open(entry_points_file_path, "r") as f:
                entry_points = json.load(f).get("entryPoints", [])

            ep = None
            for entry_point in entry_points:
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

    # -------------------------------------------------------------------------
    # Request Spec Generation (delegating to strategies)
    # -------------------------------------------------------------------------

    def _create_eval_set_run_spec(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        is_coded: bool = False,
    ) -> RequestSpec:
        """Create request spec for creating an eval set run."""
        assert self._project_id is not None, "project_id is required for SW reporting"
        strategy = self._get_strategy(is_coded)
        payload = strategy.create_eval_set_run_payload(
            eval_set_id, agent_snapshot, no_of_evals, self._project_id
        )
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/"
                f"{strategy.endpoint_suffix}evalSetRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(
        self, eval_item: EvaluationItem, eval_set_run_id: str, is_coded: bool = False
    ) -> RequestSpec:
        """Create request spec for creating an eval run."""
        strategy = self._get_strategy(is_coded)
        payload = strategy.create_eval_run_payload(eval_item, eval_set_run_id)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/"
                f"{strategy.endpoint_suffix}evalRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _update_eval_run_spec(
        self,
        evaluator_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
        is_coded: bool = False,
    ) -> RequestSpec:
        """Create request spec for updating an eval run."""
        strategy = self._get_strategy(is_coded)
        payload = strategy.create_update_eval_run_payload(
            eval_run_id,
            evaluator_runs,
            evaluator_scores,
            actual_output,
            execution_time,
            success,
        )
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/"
                f"{strategy.endpoint_suffix}evalRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _update_eval_set_run_spec(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        is_coded: bool = False,
        success: bool = True,
    ) -> RequestSpec:
        """Create request spec for updating an eval set run."""
        strategy = self._get_strategy(is_coded)
        payload = strategy.create_update_eval_set_run_payload(
            eval_set_run_id, evaluator_scores, success
        )
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/"
                f"{strategy.endpoint_suffix}evalSetRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    # -------------------------------------------------------------------------
    # API Methods
    # -------------------------------------------------------------------------

    @gracefully_handle_errors
    async def create_eval_set_run_sw(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        evaluators: list[LegacyBaseEvaluator[Any]],
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
        """Create a new evaluation run in StudioWeb."""
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
        # Separate evaluators by type
        coded_evaluators: dict[str, BaseEvaluator[Any, Any, Any]] = {}
        legacy_evaluators: dict[str, LegacyBaseEvaluator[Any]] = {}

        for k, v in evaluators.items():
            if isinstance(v, LegacyBaseEvaluator):
                legacy_evaluators[k] = v
            elif isinstance(v, BaseEvaluator):
                coded_evaluators[k] = v

        usage_metrics = self._extract_usage_from_spans(spans or [])

        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores: list[dict[str, Any]] = []

        # Use strategies for result collection
        if coded_evaluators:
            runs, scores = self._coded_strategy.collect_results(
                sw_progress_item.eval_results,
                coded_evaluators,
                usage_metrics,
                self._serialize_justification,
            )
            evaluator_runs.extend(runs)
            evaluator_scores.extend(scores)

        if legacy_evaluators:
            runs, scores = self._legacy_strategy.collect_results(
                sw_progress_item.eval_results,
                legacy_evaluators,
                usage_metrics,
                self._serialize_justification,
            )
            evaluator_runs.extend(runs)
            evaluator_scores.extend(scores)

        # Use strategy for spec generation
        spec = self._update_eval_run_spec(
            evaluator_runs=evaluator_runs,
            evaluator_scores=evaluator_scores,
            eval_run_id=sw_progress_item.eval_run_id,
            actual_output=sw_progress_item.agent_output,
            execution_time=sw_progress_item.agent_execution_time,
            success=sw_progress_item.success,
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
        success: bool = True,
    ):
        """Update the evaluation set run status to complete."""
        spec = self._update_eval_set_run_spec(
            eval_set_run_id, evaluator_scores, is_coded, success
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    async def handle_create_eval_set_run(self, payload: EvalSetRunCreatedEvent) -> None:
        try:
            self.evaluators = {eval.id: eval for eval in payload.evaluators}
            self.evaluator_scores = {eval.id: [] for eval in payload.evaluators}
            self.eval_set_execution_id = payload.execution_id

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

            if eval_set_run_id:
                await self._send_parent_trace(eval_set_run_id, payload.eval_set_id)

            logger.debug(
                f"Created eval set run with ID: {eval_set_run_id} (coded={is_coded})"
            )

        except Exception as e:
            self._format_error_message(e, "StudioWeb create eval set run error")

    async def handle_create_eval_run(self, payload: EvalRunCreatedEvent) -> None:
        try:
            if self.eval_set_execution_id and (
                eval_set_run_id := self.eval_set_run_ids.get(self.eval_set_execution_id)
            ):
                is_coded = self.is_coded_eval.get(self.eval_set_execution_id, False)
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
            eval_run_id = self.eval_run_ids.get(payload.execution_id)

            if eval_run_id:
                self.spans_exporter.trace_id = eval_run_id
            else:
                if self.eval_set_execution_id:
                    self.spans_exporter.trace_id = self.eval_set_run_ids.get(
                        self.eval_set_execution_id
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

            if eval_run_id and self.eval_set_execution_id:
                is_coded = self.is_coded_eval.get(self.eval_set_execution_id, False)
                self._extract_usage_from_spans(payload.spans)

                await self._send_evaluator_traces(
                    eval_run_id, payload.eval_results, payload.spans
                )

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
                is_coded = self.is_coded_eval.get(payload.execution_id, False)
                await self.update_eval_set_run(
                    eval_set_run_id,
                    payload.evaluator_scores,
                    is_coded=is_coded,
                    success=payload.success,
                )
                status_str = "completed" if payload.success else "failed"
                logger.debug(
                    f"Updated eval set run with ID: {eval_set_run_id} "
                    f"(coded={is_coded}, status={status_str})"
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

    # -------------------------------------------------------------------------
    # Tracing Methods
    # -------------------------------------------------------------------------

    async def _send_parent_trace(
        self, eval_set_run_id: str, eval_set_name: str
    ) -> None:
        """Send the parent trace span for the evaluation set run."""
        try:
            tracer = trace.get_tracer(__name__)
            trace_id_int = int(uuid.UUID(eval_set_run_id))

            span_context = SpanContext(
                trace_id=trace_id_int,
                span_id=trace_id_int,
                is_remote=False,
                trace_flags=TraceFlags(0x01),
            )

            ctx = trace.set_span_in_context(trace.NonRecordingSpan(span_context))

            with tracer.start_as_current_span(
                eval_set_name,
                context=ctx,
                kind=SpanKind.INTERNAL,
                start_time=int(datetime.now(timezone.utc).timestamp() * 1_000_000_000),
            ) as span:
                span.set_attribute("openinference.span.kind", "CHAIN")
                span.set_attribute("span.type", "evaluationSet")
                span.set_attribute("eval_set_run_id", eval_set_run_id)

            logger.debug(f"Created parent trace for eval set run: {eval_set_run_id}")

        except Exception as e:
            logger.warning(f"Failed to create parent trace: {e}")

    async def _send_eval_run_trace(
        self, eval_run_id: str, eval_set_run_id: str, eval_name: str
    ) -> None:
        """Send the child trace span for an evaluation run."""
        try:
            tracer = trace.get_tracer(__name__)
            trace_id_int = int(uuid.UUID(eval_run_id))
            parent_span_id_int = int(uuid.UUID(eval_set_run_id))

            parent_context = SpanContext(
                trace_id=trace_id_int,
                span_id=parent_span_id_int,
                is_remote=False,
                trace_flags=TraceFlags(0x01),
            )

            ctx = trace.set_span_in_context(trace.NonRecordingSpan(parent_context))

            with tracer.start_as_current_span(
                eval_name,
                context=ctx,
                kind=SpanKind.INTERNAL,
                start_time=int(datetime.now(timezone.utc).timestamp() * 1_000_000_000),
            ) as span:
                span.set_attribute("openinference.span.kind", "CHAIN")
                span.set_attribute("span.type", "evaluation")
                span.set_attribute("eval_run_id", eval_run_id)
                span.set_attribute("eval_set_run_id", eval_set_run_id)

            logger.debug(
                f"Created trace for eval run: {eval_run_id} (parent: {eval_set_run_id})"
            )

        except Exception as e:
            logger.warning(f"Failed to create eval run trace: {e}")

    async def _send_evaluator_traces(
        self, eval_run_id: str, eval_results: list[EvalItemResult], spans: list[Any]
    ) -> None:
        """Send trace spans for all evaluators."""
        try:
            if not eval_results:
                logger.debug(
                    f"No evaluator results to trace for eval run: {eval_run_id}"
                )
                return

            agent_readable_spans = []
            if spans:
                for span in spans:
                    if hasattr(span, "_readable_span"):
                        agent_readable_spans.append(span._readable_span())

            if agent_readable_spans:
                self.spans_exporter.export(agent_readable_spans)
                logger.debug(
                    f"Exported {len(agent_readable_spans)} agent execution spans "
                    f"for eval run: {eval_run_id}"
                )

            tracer = trace.get_tracer(__name__)
            now = datetime.now(timezone.utc)

            total_eval_time = (
                sum(
                    r.result.evaluation_time
                    for r in eval_results
                    if r.result.evaluation_time
                )
                or 0.0
            )

            parent_end_time = now
            parent_start_time = (
                datetime.fromtimestamp(
                    now.timestamp() - total_eval_time, tz=timezone.utc
                )
                if total_eval_time > 0
                else now
            )

            root_span_uuid = None
            if spans:
                from uipath.tracing._utils import _SpanUtils

                for span in spans:
                    if span.parent is None:
                        span_context = span.get_span_context()
                        root_span_uuid = _SpanUtils.span_id_to_uuid4(
                            span_context.span_id
                        )
                        break

            trace_id_int = int(uuid.UUID(eval_run_id))

            if root_span_uuid:
                root_span_id_int = int(root_span_uuid)
                parent_context = SpanContext(
                    trace_id=trace_id_int,
                    span_id=root_span_id_int,
                    is_remote=False,
                    trace_flags=TraceFlags(0x01),
                )
                ctx = trace.set_span_in_context(trace.NonRecordingSpan(parent_context))
            else:
                parent_context = SpanContext(
                    trace_id=trace_id_int,
                    span_id=trace_id_int,
                    is_remote=False,
                    trace_flags=TraceFlags(0x01),
                )
                ctx = trace.set_span_in_context(trace.NonRecordingSpan(parent_context))

            parent_start_ns = int(parent_start_time.timestamp() * 1_000_000_000)
            parent_end_ns = int(parent_end_time.timestamp() * 1_000_000_000)

            parent_span = tracer.start_span(
                "Evaluators",
                context=ctx,
                kind=SpanKind.INTERNAL,
                start_time=parent_start_ns,
            )

            parent_span.set_attribute("openinference.span.kind", "CHAIN")
            parent_span.set_attribute("span.type", "evaluators")
            parent_span.set_attribute("eval_run_id", eval_run_id)

            parent_ctx = trace.set_span_in_context(parent_span, ctx)
            current_time = parent_start_time
            readable_spans = []

            for eval_result in eval_results:
                evaluator = self.evaluators.get(eval_result.evaluator_id)
                evaluator_name = evaluator.id if evaluator else eval_result.evaluator_id

                eval_time = eval_result.result.evaluation_time or 0
                eval_start = current_time
                eval_end = datetime.fromtimestamp(
                    current_time.timestamp() + eval_time, tz=timezone.utc
                )
                current_time = eval_end

                eval_start_ns = int(eval_start.timestamp() * 1_000_000_000)
                eval_end_ns = int(eval_end.timestamp() * 1_000_000_000)

                evaluator_span = tracer.start_span(
                    evaluator_name,
                    context=parent_ctx,
                    kind=SpanKind.INTERNAL,
                    start_time=eval_start_ns,
                )

                evaluator_span.set_attribute("openinference.span.kind", "EVALUATOR")
                evaluator_span.set_attribute("span.type", "evaluator")
                evaluator_span.set_attribute("evaluator_id", eval_result.evaluator_id)
                evaluator_span.set_attribute("evaluator_name", evaluator_name)
                evaluator_span.set_attribute("eval_run_id", eval_run_id)
                evaluator_span.set_attribute("score", eval_result.result.score)
                evaluator_span.set_attribute(
                    "score_type", eval_result.result.score_type.name
                )

                if eval_result.result.details:
                    if isinstance(eval_result.result.details, BaseModel):
                        evaluator_span.set_attribute(
                            "details",
                            json.dumps(eval_result.result.details.model_dump()),
                        )
                    else:
                        evaluator_span.set_attribute(
                            "details", str(eval_result.result.details)
                        )

                if eval_result.result.evaluation_time:
                    evaluator_span.set_attribute(
                        "evaluation_time", eval_result.result.evaluation_time
                    )

                from opentelemetry.trace import Status, StatusCode

                if eval_result.result.score_type == ScoreType.ERROR:
                    evaluator_span.set_status(
                        Status(StatusCode.ERROR, "Evaluation failed")
                    )
                else:
                    evaluator_span.set_status(Status(StatusCode.OK))

                evaluator_span.end(end_time=eval_end_ns)

                if hasattr(evaluator_span, "_readable_span"):
                    readable_spans.append(evaluator_span._readable_span())

            parent_span.end(end_time=parent_end_ns)

            if hasattr(parent_span, "_readable_span"):
                readable_spans.insert(0, parent_span._readable_span())

            if readable_spans:
                self.spans_exporter.export(readable_spans)

            logger.debug(
                f"Created evaluator traces for eval run: {eval_run_id} "
                f"({len(eval_results)} evaluators)"
            )
        except Exception as e:
            logger.warning(f"Failed to create evaluator traces: {e}")
