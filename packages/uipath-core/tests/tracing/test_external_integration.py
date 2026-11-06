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


def test_run_span_provider_returns_the_span_for_the_run():
    """Test that get_run_span resolves through the registered provider."""
    from uuid import uuid4

    from uipath.core.tracing.span_utils import UiPathSpanUtils

    run_id, other_run_id = uuid4(), uuid4()
    span = trace.get_tracer("external").start_span("llm_call")
    UiPathSpanUtils.register_run_span_provider({run_id: span}.get)

    assert UiPathSpanUtils.get_run_span(run_id) is span
    assert UiPathSpanUtils.get_run_span(other_run_id) is None

    # Clean up
    UiPathSpanUtils.register_run_span_provider(None)
    span.end()


def test_run_span_without_provider_returns_none():
    """Test that get_run_span returns None when no provider is registered."""
    from uuid import uuid4

    from uipath.core.tracing.span_utils import UiPathSpanUtils

    UiPathSpanUtils.register_run_span_provider(None)

    assert UiPathSpanUtils.get_run_span(uuid4()) is None


def test_run_span_provider_raises_exception():
    """Test that exceptions from the run span provider are caught."""
    from uuid import UUID, uuid4

    from uipath.core.tracing.span_utils import UiPathSpanUtils

    def failing_provider(run_id: UUID):
        raise RuntimeError("Provider failed!")

    UiPathSpanUtils.register_run_span_provider(failing_provider)

    assert UiPathSpanUtils.get_run_span(uuid4()) is None

    # Clean up
    UiPathSpanUtils.register_run_span_provider(None)
