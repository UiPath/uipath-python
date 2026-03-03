"""Test span nesting behavior for traced decorators."""

from opentelemetry import trace

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
