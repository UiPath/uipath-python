"""Custom span processors for UiPath execution tracing."""

from typing import Callable, cast

from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)

from uipath.core.tracing.types import UiPathTraceSettings

# Hooks called synchronously in on_start (same thread as span creation, where
# ContextVar values are still live). Use register_span_start_hook to stamp
# span attributes that must survive the BatchSpanProcessor thread boundary.
_span_start_hooks: list[Callable[[Span], None]] = []


def register_span_start_hook(hook: Callable[[Span], None]) -> None:
    """Register a callable invoked for every span at creation time.

    The hook receives the live, writable Span so it can call set_attribute.
    Runs in the same thread/context as the span creator — ContextVar values
    are available here but NOT in the BatchSpanProcessor export thread.
    """
    _span_start_hooks.append(hook)


class UiPathExecutionTraceProcessorMixin:
    """Mixin that propagates execution.id and optionally filters spans."""

    _settings: UiPathTraceSettings | None = None

    def on_start(self, span: Span, parent_context: context_api.Context | None = None):
        """Called when a span is started."""
        parent_span: Span | None
        if parent_context:
            parent_span = cast(Span, trace.get_current_span(parent_context))
        else:
            parent_span = cast(Span, trace.get_current_span())

        if parent_span and parent_span.is_recording() and parent_span.attributes:
            execution_id = parent_span.attributes.get("execution.id")
            if execution_id:
                span.set_attribute("execution.id", execution_id)

        for hook in _span_start_hooks:
            hook(span)

    def on_end(self, span: ReadableSpan):
        """Called when a span ends. Filters before delegating to parent."""
        span_filter = self._settings.span_filter if self._settings else None
        if span_filter is None or span_filter(span):
            parent = cast(SpanProcessor, super())
            parent.on_end(span)


class UiPathExecutionBatchTraceProcessor(
    UiPathExecutionTraceProcessorMixin, BatchSpanProcessor
):
    """Batch span processor that propagates execution.id and optionally filters."""

    def __init__(
        self,
        span_exporter: SpanExporter,
        settings: UiPathTraceSettings | None = None,
    ):
        """Initialize the batch trace processor."""
        super().__init__(span_exporter)
        self._settings = settings


class UiPathExecutionSimpleTraceProcessor(
    UiPathExecutionTraceProcessorMixin, SimpleSpanProcessor
):
    """Simple span processor that propagates execution.id and optionally filters."""

    def __init__(
        self,
        span_exporter: SpanExporter,
        settings: UiPathTraceSettings | None = None,
    ):
        """Initialize the simple trace processor."""
        super().__init__(span_exporter)
        self._settings = settings


__all__ = [
    "UiPathExecutionBatchTraceProcessor",
    "UiPathExecutionSimpleTraceProcessor",
    "register_span_start_hook",
]
