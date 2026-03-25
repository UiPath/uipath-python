"""Tracing manager for handling tracer implementations and function registry."""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Any, ClassVar, Generator, Optional

from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.util._decorator import _AgnosticContextManager

from uipath.core.tracing.exporters import UiPathRuntimeExecutionSpanExporter
from uipath.core.tracing.processors import (
    UiPathExecutionBatchTraceProcessor,
    UiPathExecutionSimpleTraceProcessor,
)
from uipath.core.tracing.types import UiPathTraceSettings

logger = logging.getLogger(__name__)


class _DelegatingSpanProcessor(SpanProcessor):
    """A span processor that delegates to a mutable list of children.

    Registered once on the global TracerProvider. Children can be added
    and cleared between jobs without touching the provider's internal state.

    WORKAROUND: This exists because OTel's global TracerProvider is set once
    and has no public API to remove span processors. When a pod runs multiple
    jobs, each job creates a new UiPathTraceManager that adds processors to
    the same provider, causing linear accumulation of HTTP calls.
    The proper fix is for cli_server to create the TracerProvider and
    trace manager once, and register processors only at startup rather than
    per-job.
    """

    _instance: ClassVar[_DelegatingSpanProcessor | None] = None
    _init_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._processors: list[SpanProcessor] = []

    @classmethod
    def get_instance(cls, provider: TracerProvider) -> _DelegatingSpanProcessor:
        """Get or create the singleton, registering it on the provider once."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    provider.add_span_processor(cls._instance)
        return cls._instance

    def add(self, processor: SpanProcessor) -> None:
        """Add a child processor."""
        self._processors.append(processor)

    def clear(self) -> list[SpanProcessor]:
        """Remove and return all child processors."""
        removed = self._processors.copy()
        self._processors.clear()
        return removed

    def on_start(
        self, span: Span, parent_context: context_api.Context | None = None
    ) -> None:
        for p in self._processors:
            p.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        for p in self._processors:
            p.on_end(span)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return all(p.force_flush(timeout_millis) for p in self._processors)

    def shutdown(self) -> None:
        # No-op: this processor lives for the entire process lifetime.
        pass


class UiPathTraceManager:
    """Trace manager.

    Uses a single delegating processor on the global TracerProvider so that
    child processors can be added and removed between jobs without accumulation.
    """

    def __init__(self) -> None:
        """Initialize a trace manager."""
        trace.set_tracer_provider(TracerProvider())
        # If a previous provider was already set, reuse it.
        current_provider = trace.get_tracer_provider()
        assert isinstance(current_provider, TracerProvider), (
            "An incompatible Otel TracerProvider was instantiated. Please check runtime configuration."
        )
        self.tracer_provider: TracerProvider = current_provider
        self._delegating = _DelegatingSpanProcessor.get_instance(current_provider)
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
        self._delegating.add(span_processor)
        return self

    def add_span_processor(
        self,
        span_processor: SpanProcessor,
    ) -> UiPathTraceManager:
        """Add a span processor to the tracer provider."""
        self.tracer_span_processors.append(span_processor)
        self._delegating.add(span_processor)
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

    def shutdown(self) -> None:
        """Flush, shutdown, and remove all span processors registered by this manager.

        Removes child processors from the delegating processor so they no longer
        receive span events. Must be called between jobs when the same process
        handles multiple executions to prevent linear accumulation.
        """
        for processor in self.tracer_span_processors:
            try:
                processor.force_flush()
                processor.shutdown()
            except Exception:
                logger.warning(
                    "Failed to shutdown processor %s",
                    type(processor).__name__,
                    exc_info=True,
                )
        self._delegating.clear()
        self.tracer_span_processors.clear()
        self.execution_span_exporter.clear()


__all__ = ["UiPathTraceManager"]
