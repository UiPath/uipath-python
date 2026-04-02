"""Test span nesting behavior for traced decorators."""

import random

from opentelemetry import trace
from opentelemetry.trace import SpanContext, TraceFlags

from tests.conftest import SpanCapture


def test_external_span_provider_integration(span_capture: SpanCapture):
    """Test integration with external span provider."""
    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import UiPathSpanUtils

    # Create a mock external span
    external_tracer = trace.get_tracer("external")

    with external_tracer.start_as_current_span("external_span"):
        # Register a provider that returns the external span
        UiPathSpanUtils.register_current_span_provider(lambda: trace.get_current_span())

        @traced(name="internal_span")
        def internal_function():
            return "result"

        result = internal_function()

        assert result == "result"

    # Clean up
    UiPathSpanUtils.register_current_span_provider(None)

    spans = span_capture.get_spans()

    # Should have both external and internal spans
    internal_span = next((s for s in spans if s.name == "internal_span"), None)
    external_span_recorded = next((s for s in spans if s.name == "external_span"), None)

    assert internal_span is not None
    assert external_span_recorded is not None

    # Internal span should be child of external span
    assert internal_span.parent.span_id == external_span_recorded.context.span_id

    span_capture.print_hierarchy()


def test_external_span_provider_returns_none(span_capture: SpanCapture):
    """Test that None from external span provider is handled."""
    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import UiPathSpanUtils

    # Register a provider that returns None
    UiPathSpanUtils.register_current_span_provider(lambda: None)

    @traced(name="test_span")
    def test_function():
        return "result"

    result = test_function()
    assert result == "result"

    # Clean up
    UiPathSpanUtils.register_current_span_provider(None)

    spans = span_capture.get_spans()
    assert len(spans) == 1


def test_different_trace_ids_prefers_otel_current_span(span_capture: SpanCapture):
    """When OTEL current span and external span have different trace IDs,
    get_parent_context should prefer the OTEL current span (agent trace)."""
    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import UiPathSpanUtils

    # Create an OTEL span with a known trace ID (simulates agent runtime)
    agent_trace_id = random.getrandbits(128)
    agent_span_context = SpanContext(
        trace_id=agent_trace_id,
        span_id=random.getrandbits(64),
        is_remote=True,
        trace_flags=TraceFlags(0x01),
    )
    agent_span = trace.NonRecordingSpan(agent_span_context)

    # Create an external span with a DIFFERENT trace ID (simulates OpenInference)
    external_tracer = trace.get_tracer("openinference")
    external_span = external_tracer.start_span("external_span")
    assert external_span.get_span_context().trace_id != agent_trace_id

    # Register external provider that returns the external span
    UiPathSpanUtils.register_current_span_provider(lambda: external_span)

    # Set the agent span as OTEL current span and call a traced function
    with trace.use_span(agent_span, end_on_exit=False):

        @traced(name="sdk_call")
        def sdk_call():
            return "result"

        result = sdk_call()
        assert result == "result"

    external_span.end()

    # Clean up
    UiPathSpanUtils.register_current_span_provider(None)

    spans = span_capture.get_spans()
    sdk_span = next((s for s in spans if s.name == "sdk_call"), None)
    assert sdk_span is not None

    # The sdk_call span should inherit the agent's trace ID, not the external one
    assert sdk_span.context.trace_id == agent_trace_id


def test_external_span_provider_raises_exception(span_capture: SpanCapture):
    """Test that exceptions from external span provider are caught."""
    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import UiPathSpanUtils

    def failing_provider():
        raise RuntimeError("Provider failed!")

    UiPathSpanUtils.register_current_span_provider(failing_provider)

    @traced(name="test_span")
    def test_function():
        return "result"

    result = test_function()
    assert result == "result"

    # Clean up
    UiPathSpanUtils.register_current_span_provider(None)

    spans = span_capture.get_spans()
    assert len(spans) == 1
