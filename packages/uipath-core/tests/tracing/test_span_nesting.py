"""Test span nesting behavior for traced decorators."""

import pytest

from tests.conftest import SpanCapture


def test_simple_sync_nesting(span_capture: SpanCapture):
    """Test that nested sync functions create proper parent-child relationships."""
    from uipath.core.tracing.decorators import traced

    @traced(name="outer")
    def outer_function():
        return inner_function()

    @traced(name="inner")
    def inner_function():
        return "result"

    result = outer_function()

    assert result == "result"

    spans = span_capture.get_spans()
    assert len(spans) == 2, f"Expected 2 spans, got {len(spans)}"

    # Find spans by name
    inner_span = next(s for s in spans if s.name == "inner")
    outer_span = next(s for s in spans if s.name == "outer")

    # Verify parent-child relationship
    assert inner_span.parent is not None, "Inner span should have a parent"
    assert inner_span.parent.span_id == outer_span.context.span_id, (
        "Inner span's parent should be outer span"
    )

    # Verify they're in the same trace
    assert inner_span.context.trace_id == outer_span.context.trace_id, (
        "Spans should be in the same trace"
    )

    span_capture.print_hierarchy()


def test_deep_sync_nesting(span_capture: SpanCapture):
    """Test deeply nested sync functions."""
    from uipath.core.tracing.decorators import traced

    @traced(name="level1")
    def level1():
        return level2()

    @traced(name="level2")
    def level2():
        return level3()

    @traced(name="level3")
    def level3():
        return "deep_result"

    result = level1()

    assert result == "deep_result"

    spans = span_capture.get_spans()
    assert len(spans) == 3, f"Expected 3 spans, got {len(spans)}"

    # Find spans
    level1_span = next(s for s in spans if s.name == "level1")
    level2_span = next(s for s in spans if s.name == "level2")
    level3_span = next(s for s in spans if s.name == "level3")

    # Verify chain: level1 -> level2 -> level3
    assert level1_span.parent is None, "Level1 should be root"
    assert level2_span.parent.span_id == level1_span.context.span_id
    assert level3_span.parent.span_id == level2_span.context.span_id

    span_capture.print_hierarchy()


@pytest.mark.asyncio
async def test_async_nesting(span_capture: SpanCapture):
    """Test that nested async functions create proper parent-child relationships."""
    from uipath.core.tracing.decorators import traced

    @traced(name="async_outer")
    async def async_outer():
        return await async_inner()

    @traced(name="async_inner")
    async def async_inner():
        return "async_result"

    result = await async_outer()

    assert result == "async_result"

    spans = span_capture.get_spans()
    assert len(spans) == 2, f"Expected 2 spans, got {len(spans)}"

    inner_span = next(s for s in spans if s.name == "async_inner")
    outer_span = next(s for s in spans if s.name == "async_outer")

    assert inner_span.parent is not None
    assert inner_span.parent.span_id == outer_span.context.span_id

    span_capture.print_hierarchy()


@pytest.mark.asyncio
async def test_mixed_sync_async_nesting(span_capture: SpanCapture):
    """Test mixing sync and async traced functions."""
    from uipath.core.tracing.decorators import traced

    @traced(name="async_root")
    async def async_root():
        return await async_child()

    @traced(name="async_child")
    async def async_child():
        return sync_child()

    @traced(name="sync_child")
    def sync_child():
        return "mixed_result"

    result = await async_root()

    assert result == "mixed_result"

    spans = span_capture.get_spans()
    assert len(spans) == 3

    # Verify hierarchy
    async_root_span = next(s for s in spans if s.name == "async_root")
    async_child_span = next(s for s in spans if s.name == "async_child")
    sync_child_span = next(s for s in spans if s.name == "sync_child")

    assert async_child_span.parent.span_id == async_root_span.context.span_id
    assert sync_child_span.parent.span_id == async_child_span.context.span_id

    span_capture.print_hierarchy()


def test_multiple_calls_same_function(span_capture: SpanCapture):
    """Test that multiple calls to the same function create separate spans."""
    from uipath.core.tracing.decorators import traced

    @traced(name="called_multiple_times")
    def reusable_function(value):
        return value * 2

    @traced(name="caller")
    def caller():
        result1 = reusable_function(5)
        result2 = reusable_function(10)
        return result1 + result2

    result = caller()

    assert result == 30

    spans = span_capture.get_spans()
    assert len(spans) == 3, f"Expected 3 spans (1 caller + 2 calls), got {len(spans)}"

    # Find the caller span
    caller_span = next(s for s in spans if s.name == "caller")

    # Both reusable_function calls should be children of caller
    reusable_spans = [s for s in spans if s.name == "called_multiple_times"]
    assert len(reusable_spans) == 2

    for reusable_span in reusable_spans:
        assert reusable_span.parent.span_id == caller_span.context.span_id

    span_capture.print_hierarchy()


def test_sibling_functions(span_capture: SpanCapture):
    """Test that sibling function calls are handled correctly."""
    from uipath.core.tracing.decorators import traced

    @traced(name="sibling1")
    def sibling1():
        return "s1"

    @traced(name="sibling2")
    def sibling2():
        return "s2"

    @traced(name="parent")
    def parent():
        r1 = sibling1()
        r2 = sibling2()
        return r1 + r2

    result = parent()

    assert result == "s1s2"

    spans = span_capture.get_spans()
    assert len(spans) == 3

    parent_span = next(s for s in spans if s.name == "parent")
    sibling1_span = next(s for s in spans if s.name == "sibling1")
    sibling2_span = next(s for s in spans if s.name == "sibling2")

    # Both siblings should have the same parent
    assert sibling1_span.parent.span_id == parent_span.context.span_id
    assert sibling2_span.parent.span_id == parent_span.context.span_id

    span_capture.print_hierarchy()


def test_generator_nesting(span_capture: SpanCapture):
    """Test that generator functions maintain proper span nesting."""
    from uipath.core.tracing.decorators import traced

    @traced(name="generator_parent")
    def generator_parent():
        results = list(generator_child())
        return sum(results)

    @traced(name="generator_child")
    def generator_child():
        for i in range(3):
            yield i * 2

    result = generator_parent()

    assert result == 6  # 0 + 2 + 4

    spans = span_capture.get_spans()
    assert len(spans) == 2

    parent_span = next(s for s in spans if s.name == "generator_parent")
    child_span = next(s for s in spans if s.name == "generator_child")

    assert child_span.parent.span_id == parent_span.context.span_id

    span_capture.print_hierarchy()


@pytest.mark.asyncio
async def test_async_generator_nesting(span_capture: SpanCapture):
    """Test async generator nesting."""
    from uipath.core.tracing.decorators import traced

    @traced(name="async_gen_parent")
    async def async_gen_parent():
        results = []
        async for item in async_gen_child():
            results.append(item)
        return sum(results)

    @traced(name="async_gen_child")
    async def async_gen_child():
        for i in range(3):
            yield i * 3

    result = await async_gen_parent()

    assert result == 9  # 0 + 3 + 6

    spans = span_capture.get_spans()
    assert len(spans) == 2

    parent_span = next(s for s in spans if s.name == "async_gen_parent")
    child_span = next(s for s in spans if s.name == "async_gen_child")

    assert child_span.parent.span_id == parent_span.context.span_id

    span_capture.print_hierarchy()


def test_non_recording_blocks_children(span_capture: SpanCapture):
    """Test that recording=False on parent prevents children from being recorded."""
    from uipath.core.tracing.decorators import traced

    @traced(name="non_recording_parent", recording=False)
    def non_recording_parent():
        return recording_child()

    @traced(name="recording_child")
    def recording_child():
        return "result"

    result = non_recording_parent()

    assert result == "result"

    spans = span_capture.get_spans()
    # When parent has recording=False, children are also not recorded due to ParentBased sampler
    assert len(spans) == 0, (
        f"Expected 0 spans, but got {len(spans)}: {[s.name for s in spans]}"
    )

    span_capture.print_hierarchy()


def test_nested_non_recording_parents_with_external_span(span_capture: SpanCapture):
    """Test nested non-recording parents maintain hierarchy with external span provider.

    Scenario:
    1. External system (like LangGraph) creates a span manually
    2. Inside, @traced(recording=False) creates non-recording parent 1
    3. Inside that, @traced(recording=False) creates non-recording parent 2
    4. Inside that, @traced(recording=True) creates recording child

    Validates that the hierarchy is preserved:
    - non-recording parent 1 should have external_span as parent
    - non-recording parent 2 should have non-recording parent 1 as parent
    - Recording child should recognize non-recording parent 2 as the deeper parent
    """
    from opentelemetry import trace

    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import UiPathSpanUtils, _span_registry

    # Simulate external system (like LangGraph) creating a span manually
    external_tracer = trace.get_tracer("external_system")
    with external_tracer.start_as_current_span("external_span") as external_span:
        stored_external_span = external_span

        # Register this as the external span provider
        UiPathSpanUtils.register_current_span_provider(lambda: stored_external_span)

        try:

            @traced(name="non_recording_parent_1", recording=False)
            def non_recording_parent_1():
                return non_recording_parent_2()

            @traced(name="non_recording_parent_2", recording=False)
            def non_recording_parent_2():
                return recording_child()

            @traced(name="recording_child", recording=True)
            def recording_child():
                return "child_result"

            result = non_recording_parent_1()
            assert result == "child_result"

            external_span_id = stored_external_span.get_span_context().span_id
        finally:
            UiPathSpanUtils.register_current_span_provider(None)

    spans = span_capture.get_spans()

    # Should have: external_span only (non-recording spans aren't recorded)
    external_span_recorded = next((s for s in spans if s.name == "external_span"), None)
    assert external_span_recorded is not None, "external_span should be recorded"

    # Find non-recording parents in SpanRegistry
    non_recording_parent_1_id = None
    non_recording_parent_2_id = None

    for span_id, parent_id in _span_registry._parent_map.items():
        stored_span = _span_registry.get_span(span_id)
        if stored_span is not None:
            # Find parent 1 (direct child of external_span)
            if parent_id == external_span_id:
                non_recording_parent_1_id = span_id
            # Find parent 2 (child of parent 1)
            elif (
                parent_id == non_recording_parent_1_id
                and non_recording_parent_1_id is not None
            ):
                non_recording_parent_2_id = span_id

    assert non_recording_parent_1_id is not None, (
        "BUG: non_recording_parent_1 should be registered in SpanRegistry "
        "with external_span as its parent"
    )
    assert non_recording_parent_2_id is not None, (
        "BUG: non_recording_parent_2 should be registered in SpanRegistry "
        "with non_recording_parent_1 as its parent"
    )

    # Verify the hierarchy and depths
    parent_1_parent = _span_registry.get_parent_id(non_recording_parent_1_id)
    parent_2_parent = _span_registry.get_parent_id(non_recording_parent_2_id)

    assert parent_1_parent == external_span_id, (
        f"non_recording_parent_1 should have external_span as parent, "
        f"got {parent_1_parent}"
    )
    assert parent_2_parent == non_recording_parent_1_id, (
        f"non_recording_parent_2 should have non_recording_parent_1 as parent, "
        f"got {parent_2_parent}"
    )

    # Verify depths: external=0, parent_1=1, parent_2=2
    external_depth = _span_registry.calculate_depth(external_span_id)
    parent_1_depth = _span_registry.calculate_depth(non_recording_parent_1_id)
    parent_2_depth = _span_registry.calculate_depth(non_recording_parent_2_id)

    assert external_depth == 0, (
        f"External span should have depth 0, got {external_depth}"
    )
    assert parent_1_depth == 1, (
        f"non_recording_parent_1 should have depth 1 (parent=external), got {parent_1_depth}"
    )
    assert parent_2_depth == 2, (
        f"non_recording_parent_2 should have depth 2 (parent=parent_1), got {parent_2_depth}"
    )

    # Verify the fix: _get_bottom_most_span should recognize parent 2 as deepest
    # This simulates what child calls get_parent_context()
    current_span_mock = _span_registry.get_span(non_recording_parent_2_id)
    external_span_mock = external_span_recorded

    if current_span_mock is not None:
        bottom_span = UiPathSpanUtils._get_bottom_most_span(
            current_span_mock, external_span_mock
        )
        assert bottom_span.get_span_context().span_id == non_recording_parent_2_id, (
            "BUG: _get_bottom_most_span should return non_recording_parent_2 (deepest), "
            f"but returned {bottom_span.get_span_context().span_id}"
        )

    _span_registry.clear()
    span_capture.print_hierarchy()


def test_non_recording_parent_picks_external_when_outside_context(
    span_capture: SpanCapture,
):
    """Test that non-recording parent correctly picks external span when called outside OTel context.

    Scenario:
    1. External span provider is registered and stored
    2. Exit the OTel context (so trace.get_current_span() returns default/invalid)
    3. @traced(recording=False) is called OUTSIDE the context

    The test: Non-recording parent should have the external span as parent.

    This test fails with: parent_context = trace.get_current_span().get_span_context()
    Because outside the context, trace.get_current_span() returns a default NonRecordingSpan,
    not the external span we want.

    This test passes with: parent_context from get_parent_context() logic
    Because get_parent_context() checks both current (invalid) and external (valid),
    and picks the external one.
    """
    from opentelemetry import trace

    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import UiPathSpanUtils, _span_registry

    # Create external span INSIDE a context
    external_tracer = trace.get_tracer("external_system")
    external_span_cm = external_tracer.start_as_current_span("external_span")
    external_span = external_span_cm.__enter__()
    external_span_id = external_span.get_span_context().span_id

    # Store and register the external span
    stored_external_span = external_span
    UiPathSpanUtils.register_current_span_provider(lambda: stored_external_span)

    # Exit the OTel context manager
    external_span_cm.__exit__(None, None, None)

    # NOW we're OUTSIDE the context - trace.get_current_span() returns default/invalid
    # But the external provider is still active

    try:

        @traced(name="non_recording_parent", recording=False)
        def non_recording_parent():
            return "result"

        result = non_recording_parent()
        assert result == "result"

        # The non-recording parent should have the external span as parent
        # NOT the invalid span from trace.get_current_span()
        non_recording_parent_id = None
        for span_id, parent_id in _span_registry._parent_map.items():
            if parent_id == external_span_id:
                stored_span = _span_registry.get_span(span_id)
                if stored_span is not None:
                    non_recording_parent_id = span_id
                    break

        assert non_recording_parent_id is not None, (
            "Non-recording parent should be parented to external_span. "
            "With trace.get_current_span() directly, it would pick an invalid/default span instead."
        )

        # Verify hierarchy
        non_recording_depth = _span_registry.calculate_depth(non_recording_parent_id)
        external_depth = _span_registry.calculate_depth(external_span_id)

        assert external_depth == 0, (
            f"External span should have depth 0, got {external_depth}"
        )
        assert non_recording_depth == 1, (
            f"Non-recording parent should have depth 1 (parent=external), got {non_recording_depth}"
        )

        _span_registry.clear()
    finally:
        UiPathSpanUtils.register_current_span_provider(None)


def test_ctx_parameter_required_when_external_deeper_than_current(
    span_capture: SpanCapture,
):
    """Test that trace.get_current_span(ctx) is required when external span is deeper.

    Scenario:
    1. Create an external span (depth 0)
    2. Create a deeper nested external span (depth 1) - this becomes current external
    3. Create an OTel span INSIDE the deepest external context
    4. Register the deepest external span as the external provider
    5. Create a non-recording span

    Expected behavior with trace.get_current_span(ctx):
    - get_parent_context() compares: current OTel span vs external span
    - External span is deeper (depth 1), so it's chosen
    - trace.get_current_span(ctx) gets the external span from ctx
    - Non-recording span is parented to external

    Bug with trace.get_current_span() without ctx:
    - trace.get_current_span() (no args) returns the OTel span (from thread-local)
    - Non-recording span gets parented to OTel span (wrong!)

    This test PASSES with the fix (ctx parameter) and FAILS without it.
    """
    from opentelemetry import trace

    from uipath.core.tracing.decorators import traced
    from uipath.core.tracing.span_utils import UiPathSpanUtils, _span_registry

    # Step 1: Create external span hierarchy
    external_tracer = trace.get_tracer("external_system")

    # Create external_root (depth 0)
    external_root_cm = external_tracer.start_as_current_span("external_root")
    external_root = external_root_cm.__enter__()
    external_root_id = external_root.get_span_context().span_id

    # Create external_deep (depth 1) - child of external_root
    external_deep_cm = external_tracer.start_as_current_span("external_deep")
    external_deep = external_deep_cm.__enter__()
    external_deep_id = external_deep.get_span_context().span_id

    # Register external_deep as the external provider BEFORE exiting context
    UiPathSpanUtils.register_current_span_provider(lambda: external_deep)

    # Exit the external context to create a separate branch
    external_deep_cm.__exit__(None, None, None)
    external_root_cm.__exit__(None, None, None)

    # NOW create OTel span in a SEPARATE context (not inside external_deep)
    otel_tracer = trace.get_tracer(__name__)
    otel_span_cm = otel_tracer.start_as_current_span("otel_span")
    otel_span = otel_span_cm.__enter__()
    otel_span_id = otel_span.get_span_context().span_id

    try:
        from uipath.core.tracing.span_utils import ParentedNonRecordingSpan

        # Register external spans with parent relationship
        _span_registry.register_span(external_root)
        _span_registry.register_span(external_deep)

        # Register OTel span as ParentedNonRecordingSpan with NO parent
        # (This simulates OTel span in a separate branch)
        otel_span_context = otel_span.get_span_context()
        otel_span_tracked = ParentedNonRecordingSpan(otel_span_context, parent=None)
        _span_registry.register_span(otel_span_tracked)

        # Verify depths
        external_root_depth = _span_registry.calculate_depth(external_root_id)
        external_deep_depth = _span_registry.calculate_depth(external_deep_id)
        otel_depth = _span_registry.calculate_depth(otel_span_id)

        assert external_root_depth == 0, (
            f"External root depth should be 0, got {external_root_depth}"
        )
        assert external_deep_depth == 1, (
            f"External deep depth should be 1, got {external_deep_depth}"
        )
        assert otel_depth == 0, (
            f"OTel span depth should be 0 (no parent), got {otel_depth}"
        )

        # Verify external_deep is deeper than otel_span
        assert external_deep_depth > otel_depth, (
            "External deep should be deeper than otel span"
        )

        # Create non-recording span INSIDE the otel_span context
        @traced(name="non_recording_inside_otel", recording=False)
        def non_recording_func():
            # Add a recording child inside the non-recording parent
            return recording_child_func()

        @traced(name="recording_child_of_non_recording", recording=True)
        def recording_child_func():
            return "child_result"

        result = non_recording_func()
        assert result == "child_result"

        # Get all spans captured
        captured_spans = span_capture.get_spans()

        # Verify that neither non-recording nor its recording child are in the captured spans
        # (because the parent was non-recording, children should not be recorded per ParentBased sampler)
        captured_span_names = [s.name for s in captured_spans]
        assert "non_recording_inside_otel" not in captured_span_names, (
            "Non-recording span should not be captured in span_capture"
        )
        assert "recording_child_of_non_recording" not in captured_span_names, (
            "Recording child of non-recording parent should not be captured due to ParentBased sampler"
        )

        # Step 2: Verify the non-recording span was parented to external_deep (deeper)
        # NOT to otel_span (which is current in thread-local context)
        non_recording_id = None
        for span_id, parent_id in _span_registry._parent_map.items():
            stored_span = _span_registry.get_span(span_id)
            if stored_span is not None and parent_id == external_deep_id:
                non_recording_id = span_id
                break

        assert non_recording_id is not None, (
            "CRITICAL: Non-recording span should be parented to external_deep (deeper). "
            "This requires using trace.get_current_span(ctx) NOT trace.get_current_span(). "
            "With trace.get_current_span() alone, it would pick the OTel span "
            "(which is current in thread-local context), not the external span."
        )

        # Verify it's NOT parented to the OTel span
        for _span_id, parent_id in _span_registry._parent_map.items():
            if parent_id == otel_span_id:
                raise AssertionError(
                    "Non-recording span should NOT be parented to otel_span. "
                    "This indicates trace.get_current_span() was used instead of trace.get_current_span(ctx)."
                )

        _span_registry.clear()

    finally:
        otel_span_cm.__exit__(None, None, None)
        UiPathSpanUtils.register_current_span_provider(None)
