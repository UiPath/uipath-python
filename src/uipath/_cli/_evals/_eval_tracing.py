"""Tracing utilities for evaluation reporting."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags
from pydantic import BaseModel

from uipath.eval.models import EvalItemResult, ScoreType
from uipath.tracing import LlmOpsHttpExporter

logger = logging.getLogger(__name__)


class EvalTracingManager:
    """Manages OpenTelemetry tracing for evaluation runs."""

    def __init__(
        self,
        spans_exporter: LlmOpsHttpExporter,
        evaluators: dict[str, Any],
    ):
        """Initialize the tracing manager.

        Args:
            spans_exporter: The LlmOps HTTP exporter for sending spans.
            evaluators: Dict of evaluator ID to evaluator instance.
        """
        self._spans_exporter = spans_exporter
        self._evaluators = evaluators
        self._tracer = trace.get_tracer(__name__)

    def set_trace_id(self, trace_id: str | None) -> None:
        """Set the trace ID on the spans exporter.

        Args:
            trace_id: The trace ID to set.
        """
        self._spans_exporter.trace_id = trace_id

    def export_spans(self, spans: list[Any]) -> None:
        """Export spans via the spans exporter.

        Args:
            spans: List of spans to export.
        """
        self._spans_exporter.export(spans)

    async def send_parent_trace(self, eval_set_run_id: str, eval_set_name: str) -> None:
        """Send the parent trace span for the evaluation set run.

        Args:
            eval_set_run_id: The ID of the evaluation set run.
            eval_set_name: The name of the evaluation set.
        """
        try:
            trace_id_int = int(uuid.UUID(eval_set_run_id))

            span_context = SpanContext(
                trace_id=trace_id_int,
                span_id=trace_id_int,
                is_remote=False,
                trace_flags=TraceFlags(0x01),
            )

            ctx = trace.set_span_in_context(trace.NonRecordingSpan(span_context))

            with self._tracer.start_as_current_span(
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

    async def send_eval_run_trace(
        self, eval_run_id: str, eval_set_run_id: str, eval_name: str
    ) -> None:
        """Send the child trace span for an evaluation run.

        Args:
            eval_run_id: The ID of the evaluation run.
            eval_set_run_id: The ID of the parent evaluation set run.
            eval_name: The name of the evaluation.
        """
        try:
            trace_id_int = int(uuid.UUID(eval_run_id))
            parent_span_id_int = int(uuid.UUID(eval_set_run_id))

            parent_context = SpanContext(
                trace_id=trace_id_int,
                span_id=parent_span_id_int,
                is_remote=False,
                trace_flags=TraceFlags(0x01),
            )

            ctx = trace.set_span_in_context(trace.NonRecordingSpan(parent_context))

            with self._tracer.start_as_current_span(
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

    async def send_evaluator_traces(
        self, eval_run_id: str, eval_results: list[EvalItemResult], spans: list[Any]
    ) -> None:
        """Send trace spans for all evaluators.

        Args:
            eval_run_id: The ID of the evaluation run.
            eval_results: List of evaluator results.
            spans: List of spans that may contain evaluator LLM calls.
        """
        try:
            if not eval_results:
                logger.debug(
                    f"No evaluator results to trace for eval run: {eval_run_id}"
                )
                return

            # Export agent execution spans
            self._export_agent_spans(spans, eval_run_id)

            # Calculate timing
            now = datetime.now(timezone.utc)
            total_eval_time = sum(
                (
                    r.result.evaluation_time
                    for r in eval_results
                    if r.result.evaluation_time
                ),
                0.0,
            )

            parent_end_time = now
            parent_start_time = (
                datetime.fromtimestamp(
                    now.timestamp() - total_eval_time, tz=timezone.utc
                )
                if total_eval_time > 0
                else now
            )

            # Find root span and create context
            ctx = self._create_evaluators_context(eval_run_id, spans)

            # Create parent span
            parent_start_ns = int(parent_start_time.timestamp() * 1_000_000_000)
            parent_end_ns = int(parent_end_time.timestamp() * 1_000_000_000)

            parent_span = self._tracer.start_span(
                "Evaluators",
                context=ctx,
                kind=SpanKind.INTERNAL,
                start_time=parent_start_ns,
            )
            parent_span.set_attribute("openinference.span.kind", "CHAIN")
            parent_span.set_attribute("span.type", "evaluators")
            parent_span.set_attribute("eval_run_id", eval_run_id)

            parent_ctx = trace.set_span_in_context(parent_span, ctx)

            # Create individual evaluator spans
            readable_spans = []
            current_time = parent_start_time

            for eval_result in eval_results:
                evaluator_span, eval_end = self._create_evaluator_span(
                    eval_result, eval_run_id, current_time, parent_ctx
                )
                current_time = eval_end

                if hasattr(evaluator_span, "_readable_span"):
                    readable_spans.append(evaluator_span._readable_span())

            # End parent span
            parent_span.end(end_time=parent_end_ns)
            if hasattr(parent_span, "_readable_span"):
                readable_spans.insert(0, parent_span._readable_span())

            # Export all spans
            if readable_spans:
                self._spans_exporter.export(readable_spans)

            logger.debug(
                f"Created evaluator traces for eval run: {eval_run_id} ({len(eval_results)} evaluators)"
            )

        except Exception as e:
            logger.warning(f"Failed to create evaluator traces: {e}")

    def _export_agent_spans(self, spans: list[Any], eval_run_id: str) -> None:
        """Export agent execution spans.

        Args:
            spans: List of agent execution spans.
            eval_run_id: The evaluation run ID for logging.
        """
        agent_readable_spans = []
        if spans:
            for span in spans:
                if hasattr(span, "_readable_span"):
                    agent_readable_spans.append(span._readable_span())

        if agent_readable_spans:
            self._spans_exporter.export(agent_readable_spans)
            logger.debug(
                f"Exported {len(agent_readable_spans)} agent execution spans for eval run: {eval_run_id}"
            )

    def _create_evaluators_context(self, eval_run_id: str, spans: list[Any]) -> Any:
        """Create the context for evaluator spans.

        Args:
            eval_run_id: The evaluation run ID.
            spans: List of agent spans to find root span from.

        Returns:
            OpenTelemetry context for creating child spans.
        """
        trace_id_int = int(uuid.UUID(eval_run_id))

        # Find root span from agent spans
        root_span_uuid = None
        if spans:
            from uipath.tracing._utils import _SpanUtils

            for span in spans:
                if span.parent is None:
                    span_context = span.get_span_context()
                    root_span_uuid = _SpanUtils.span_id_to_uuid4(span_context.span_id)
                    break

        if root_span_uuid:
            root_span_id_int = int(root_span_uuid)
            parent_context = SpanContext(
                trace_id=trace_id_int,
                span_id=root_span_id_int,
                is_remote=False,
                trace_flags=TraceFlags(0x01),
            )
        else:
            parent_context = SpanContext(
                trace_id=trace_id_int,
                span_id=trace_id_int,
                is_remote=False,
                trace_flags=TraceFlags(0x01),
            )

        return trace.set_span_in_context(trace.NonRecordingSpan(parent_context))

    def _create_evaluator_span(
        self,
        eval_result: EvalItemResult,
        eval_run_id: str,
        start_time: datetime,
        parent_ctx: Any,
    ) -> tuple[Any, datetime]:
        """Create a single evaluator span.

        Args:
            eval_result: The evaluator result.
            eval_run_id: The evaluation run ID.
            start_time: Start time for this evaluator.
            parent_ctx: Parent context for the span.

        Returns:
            Tuple of (span, end_time).
        """
        evaluator = self._evaluators.get(eval_result.evaluator_id)
        evaluator_name = evaluator.id if evaluator else eval_result.evaluator_id

        eval_time = eval_result.result.evaluation_time or 0
        eval_end = datetime.fromtimestamp(
            start_time.timestamp() + eval_time, tz=timezone.utc
        )

        eval_start_ns = int(start_time.timestamp() * 1_000_000_000)
        eval_end_ns = int(eval_end.timestamp() * 1_000_000_000)

        evaluator_span = self._tracer.start_span(
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
        evaluator_span.set_attribute("score_type", eval_result.result.score_type.name)

        if eval_result.result.details:
            if isinstance(eval_result.result.details, BaseModel):
                evaluator_span.set_attribute(
                    "details", json.dumps(eval_result.result.details.model_dump())
                )
            else:
                evaluator_span.set_attribute("details", str(eval_result.result.details))

        if eval_result.result.evaluation_time:
            evaluator_span.set_attribute(
                "evaluation_time", eval_result.result.evaluation_time
            )

        if eval_result.result.score_type == ScoreType.ERROR:
            evaluator_span.set_status(Status(StatusCode.ERROR, "Evaluation failed"))
        else:
            evaluator_span.set_status(Status(StatusCode.OK))

        evaluator_span.end(end_time=eval_end_ns)

        return evaluator_span, eval_end
