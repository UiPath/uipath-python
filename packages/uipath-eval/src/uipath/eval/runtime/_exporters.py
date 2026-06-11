import logging
from collections import defaultdict
from typing import Sequence

from opentelemetry import context as context_api
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)
from uipath.core.tracing.processors import UiPathExecutionBatchTraceProcessor
from uipath.runtime.logging import UiPathRuntimeExecutionLogHandler

from .._execution_context import ExecutionSpanCollector, execution_id_context


class ExecutionSpanExporter(SpanExporter):
    """Custom exporter that stores spans grouped by execution ids."""

    def __init__(self):
        # { execution_id -> list of spans }
        self._spans: dict[str, list[ReadableSpan]] = defaultdict(list)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            if span.attributes is not None:
                exec_id = span.attributes.get("execution.id")
                if exec_id is not None and isinstance(exec_id, str):
                    self._spans[exec_id].append(span)

        return SpanExportResult.SUCCESS

    def get_spans(self, execution_id: str) -> list[ReadableSpan]:
        """Retrieve spans for a given execution id."""
        return self._spans.get(execution_id, [])

    def clear(self, execution_id: str | None = None) -> None:
        """Clear stored spans for one or all executions."""
        if execution_id:
            self._spans.pop(execution_id, None)
        else:
            self._spans.clear()

    def shutdown(self) -> None:
        self.clear()


class ExecutionSpanProcessor(UiPathExecutionBatchTraceProcessor):
    """Span processor that adds spans to ExecutionSpanCollector when they start."""

    def __init__(self, span_exporter: SpanExporter, collector: ExecutionSpanCollector):
        super().__init__(span_exporter)
        self.collector = collector

    def on_start(
        self, span: Span, parent_context: context_api.Context | None = None
    ) -> None:
        super().on_start(span, parent_context)

        exec_id = span.attributes.get("execution.id") if span.attributes else None

        # Fallback: if execution.id wasn't propagated (e.g., NonRecordingSpan
        # parent on resume), get it from the execution context variable.
        if exec_id is None:
            ctx_exec_id = execution_id_context.get()
            if ctx_exec_id:
                span.set_attribute("execution.id", ctx_exec_id)
                exec_id = ctx_exec_id

        if span.attributes and "execution.id" in span.attributes:
            exec_id = span.attributes["execution.id"]
            if isinstance(exec_id, str):
                self.collector.add_span(span, exec_id)


class ExecutionLogsExporter:
    """Custom exporter that stores multiple execution log handlers."""

    def __init__(self):
        self._log_handlers: dict[str, UiPathRuntimeExecutionLogHandler] = {}

    def register(
        self, execution_id: str, handler: UiPathRuntimeExecutionLogHandler
    ) -> None:
        self._log_handlers[execution_id] = handler

    def get_logs(self, execution_id: str) -> list[logging.LogRecord]:
        """Clear stored spans for one or all executions."""
        log_handler = self._log_handlers.get(execution_id)
        return log_handler.buffer if log_handler else []

    def clear(self, execution_id: str | None = None) -> None:
        """Clear stored spans for one or all executions."""
        if execution_id:
            self._log_handlers.pop(execution_id, None)
        else:
            self._log_handlers.clear()
