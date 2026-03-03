"""Test span registry and parent context resolution."""

from opentelemetry.trace import Span

from tests.conftest import SpanCapture
from uipath.core.tracing.decorators import traced
from uipath.core.tracing.span_utils import UiPathSpanUtils, _span_registry


def test_nested_traced_functions_with_external_context(span_capture: SpanCapture):
    """Test nested traced functions when external span context is provided.

    Simulates the scenario where:
    - An external tracing system (like LangGraph) has active spans
    - Our traced decorators create OTel spans
    - The registry determines which span is deeper
    """

    external_span_stack: list[Span] = []

    def mock_external_span_provider():
        return external_span_stack[-1] if external_span_stack else None

    def mock_ancestors_provider():
        return list(external_span_stack)

    UiPathSpanUtils.register_current_span_provider(mock_external_span_provider)
    UiPathSpanUtils.register_current_span_ancestors_provider(mock_ancestors_provider)

    @traced(name="root")
    def root():
        spans = span_capture.get_spans()
        if spans:
            external_span_stack.append(spans[-1])

        result = level1()

        if external_span_stack:
            external_span_stack.pop()

        return result

    @traced(name="level1")
    def level1():
        return level2()

    @traced(name="level2")
    def level2():
        return level3()

    @traced(name="level3")
    def level3():
        return level4()

    @traced(name="level4")
    def level4():
        return level5()

    @traced(name="level5")
    def level5():
        return "done"

    result = root()

    assert result == "done"

    spans = span_capture.get_spans()
    assert len(spans) == 6, f"Expected 6 spans, got {len(spans)}"

    root_span = next(s for s in spans if s.name == "root")
    level1_span = next(s for s in spans if s.name == "level1")
    level2_span = next(s for s in spans if s.name == "level2")
    level3_span = next(s for s in spans if s.name == "level3")
    level4_span = next(s for s in spans if s.name == "level4")
    level5_span = next(s for s in spans if s.name == "level5")

    # Verify hierarchy
    assert root_span.parent is None, "Root should have no parent"
    assert level1_span.parent is not None
    assert level1_span.parent.span_id == root_span.context.span_id
    assert level2_span.parent is not None
    assert level2_span.parent.span_id == level1_span.context.span_id
    assert level3_span.parent is not None
    assert level3_span.parent.span_id == level2_span.context.span_id
    assert level4_span.parent is not None
    assert level4_span.parent.span_id == level3_span.context.span_id
    assert level5_span.parent is not None
    assert level5_span.parent.span_id == level4_span.context.span_id

    span_capture.print_hierarchy()

    # Cleanup
    UiPathSpanUtils.register_current_span_provider(None)
    UiPathSpanUtils.register_current_span_ancestors_provider(None)


def test_span_registry_depth_calculation(span_capture: SpanCapture):
    """Test that the span registry correctly calculates span depths."""
    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import _span_registry

    @traced(name="depth0")
    def depth0():
        return depth1()

    @traced(name="depth1")
    def depth1():
        return depth2()

    @traced(name="depth2")
    def depth2():
        return depth3()

    @traced(name="depth3")
    def depth3():
        return "max_depth"

    result = depth0()

    assert result == "max_depth"

    spans = span_capture.get_spans()
    assert len(spans) == 4

    # Register all spans in the registry
    for span in spans:
        _span_registry.register_span(span)

    # Get span IDs
    depth0_span = next(s for s in spans if s.name == "depth0")
    depth1_span = next(s for s in spans if s.name == "depth1")
    depth2_span = next(s for s in spans if s.name == "depth2")
    depth3_span = next(s for s in spans if s.name == "depth3")

    # Verify depths
    assert _span_registry.calculate_depth(depth0_span.context.span_id) == 0
    assert _span_registry.calculate_depth(depth1_span.context.span_id) == 1
    assert _span_registry.calculate_depth(depth2_span.context.span_id) == 2
    assert _span_registry.calculate_depth(depth3_span.context.span_id) == 3

    span_capture.print_hierarchy()


def test_span_registry_is_ancestor(span_capture: SpanCapture):
    """Test that the span registry correctly identifies ancestor relationships."""

    @traced(name="grandparent")
    def grandparent():
        return parent()

    @traced(name="parent")
    def parent():
        return child()

    @traced(name="child")
    def child():
        return "leaf"

    result = grandparent()

    assert result == "leaf"

    spans = span_capture.get_spans()
    assert len(spans) == 3

    # Register all spans
    for span in spans:
        _span_registry.register_span(span)

    grandparent_span = next(s for s in spans if s.name == "grandparent")
    parent_span = next(s for s in spans if s.name == "parent")
    child_span = next(s for s in spans if s.name == "child")

    grandparent_id = grandparent_span.context.span_id
    parent_id = parent_span.context.span_id
    child_id = child_span.context.span_id

    # Test ancestor relationships
    assert _span_registry.is_ancestor(grandparent_id, child_id), (
        "Grandparent should be ancestor of child"
    )
    assert _span_registry.is_ancestor(parent_id, child_id), (
        "Parent should be ancestor of child"
    )
    assert _span_registry.is_ancestor(grandparent_id, parent_id), (
        "Grandparent should be ancestor of parent"
    )

    # Test negative cases
    assert not _span_registry.is_ancestor(child_id, grandparent_id), (
        "Child should not be ancestor of grandparent"
    )
    assert not _span_registry.is_ancestor(parent_id, grandparent_id), (
        "Parent should not be ancestor of grandparent"
    )

    span_capture.print_hierarchy()


def test_mixed_otel_and_external_spans(span_capture: SpanCapture):
    """Test scenario where OTel spans and external spans are interleaved.

    This mimics the real-world scenario from the screenshots where:
    - LangGraph creates spans
    - generate_report is traced
    - Custom traced functions are called
    - All should maintain proper hierarchy
    """

    external_spans: list[Span] = []

    def mock_external_span_provider():
        return external_spans[-1] if external_spans else None

    def mock_ancestors_provider():
        return external_spans[:-1] if len(external_spans) > 1 else []

    UiPathSpanUtils.register_current_span_provider(mock_external_span_provider)
    UiPathSpanUtils.register_current_span_ancestors_provider(mock_ancestors_provider)

    @traced(name="langraph_simulation")
    def langraph_simulation():
        spans = span_capture.get_spans()
        if spans:
            external_spans.append(spans[-1])

        result = generate_report()

        if external_spans:
            external_spans.pop()

        return result

    @traced(name="generate_report")
    def generate_report():
        spans = span_capture.get_spans()
        if spans:
            # Add generate_report to external spans
            for s in spans:
                if s.name == "generate_report" and s not in external_spans:
                    external_spans.append(s)
                    break

        result = custom_function()

        # Remove generate_report from external spans
        if (
            external_spans
            and getattr(external_spans[-1], "name", None) == "generate_report"
        ):
            external_spans.pop()

        return result

    @traced(name="custom_function")
    def custom_function():
        return nested_function()

    @traced(name="nested_function")
    def nested_function():
        return "result"

    result = langraph_simulation()

    assert result == "result"

    spans = span_capture.get_spans()
    assert len(spans) >= 4, f"Expected at least 4 spans, got {len(spans)}"

    # Verify hierarchy
    langraph_span = next(s for s in spans if s.name == "langraph_simulation")
    report_span = next(s for s in spans if s.name == "generate_report")
    custom_span = next(s for s in spans if s.name == "custom_function")
    nested_span = next(s for s in spans if s.name == "nested_function")

    # Check parent-child relationships
    assert report_span.parent is not None
    assert report_span.parent.span_id == langraph_span.context.span_id

    assert custom_span.parent is not None
    assert custom_span.parent.span_id == report_span.context.span_id

    assert nested_span.parent is not None
    assert nested_span.parent.span_id == custom_span.context.span_id

    span_capture.print_hierarchy()

    # Cleanup
    UiPathSpanUtils.register_current_span_provider(None)
    UiPathSpanUtils.register_current_span_ancestors_provider(None)
