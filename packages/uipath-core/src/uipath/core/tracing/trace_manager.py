"""Tracing manager for handling tracer implementations and function registry."""

from __future__ import annotations

import contextlib
from typing import Any, Generator, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.util._decorator import _AgnosticContextManager

from uipath.core.tracing.exporters import UiPathRuntimeExecutionSpanExporter
from uipath.core.tracing.processors import (
    UiPathExecutionBatchTraceProcessor,
    UiPathExecutionSimpleTraceProcessor,
)
from uipath.core.tracing.types import UiPathTraceSettings


class UiPathTraceManager:
    """Trace manager.

    NOTE: Instantiate trace manager only once.
    """

    def __init__(self):
        """Initialize a trace manager."""
        trace.set_tracer_provider(TracerProvider())
        # If a previous provider set, reuse it.
        current_provider = trace.get_tracer_provider()
        assert isinstance(current_provider, TracerProvider), (
            "An incompatible Otel TracerProvider was instantiated. Please check runtime configuration."
        )
        self.tracer_provider: TracerProvider = current_provider
        self.tracer_span_processors: list[SpanProcessor] = []
        self.execution_span_exporter = UiPathRuntimeExecutionSpanExporter()
        self.add_span_exporter(self.execution_span_exporter)

    def add_span_exporter(
        self,
        span_exporter: SpanExporter,
        batch: bool = True,
        settings: UiPathTraceSettings | None = None,
    ) -> UiPathTraceManager:
        """Add a span exporter to the tracer provider.

        Args:
            span_exporter: The exporter to add.
            batch: Whether to use batch processing (default: True).
            settings: Optional trace settings for filtering, etc.
        """
        span_processor: SpanProcessor
        if batch:
            span_processor = UiPathExecutionBatchTraceProcessor(span_exporter, settings)
        else:
            span_processor = UiPathExecutionSimpleTraceProcessor(
                span_exporter, settings
            )
        self.tracer_span_processors.append(span_processor)
        self.tracer_provider.add_span_processor(span_processor)
        return self

    def add_span_processor(
        self,
        span_processor: SpanProcessor,
    ) -> UiPathTraceManager:
        """Add a span processor to the tracer provider."""
        self.tracer_span_processors.append(span_processor)
        self.tracer_provider.add_span_processor(span_processor)
        return self

    def get_execution_spans(
        self,
        execution_id: str,
    ) -> list[ReadableSpan]:
        """Retrieve spans for a given execution id."""
        return self.execution_span_exporter.get_spans(execution_id)

    @contextlib.contextmanager
    def start_execution_span(
        self,
        root_span: str,
        execution_id: str,
        attributes: Optional[dict[str, str]] = None,
    ) -> Generator[_AgnosticContextManager[Any] | Any, Any, None]:
        """Start an execution span."""
        try:
            tracer = trace.get_tracer("uipath-runtime")
            span_attributes: dict[str, Any] = {}
            if execution_id:
                span_attributes["execution.id"] = execution_id
            if attributes:
                span_attributes.update(attributes)
            with tracer.start_as_current_span(
                root_span, attributes=span_attributes
            ) as span:
                yield span
        finally:
            self.flush_spans()

    def flush_spans(self) -> None:
        """Flush all span processors."""
        for span_processor in self.tracer_span_processors:
            span_processor.force_flush()


__all__ = ["UiPathTraceManager"]
