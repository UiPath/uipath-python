"""Simple test for runtime factory and executor span capture."""

import pytest
from opentelemetry import trace

from uipath.core.tracing.trace_manager import UiPathTraceManager


@pytest.mark.asyncio
async def test_multiple_factories_same_executor():
    """Test two factories using same executor, verify spans are captured correctly."""
    trace_manager = UiPathTraceManager()

    # Create span
    tracer = trace.get_tracer("uipath-runtime")
    with trace_manager.start_execution_span("root-span", "test"):
        with tracer.start_as_current_span(
            "custom-child-span", attributes={"operation": "child", "step": "1"}
        ):
            pass

    spans = trace_manager.get_execution_spans("test")
    assert len(spans) == 2

    assert spans[0].name == "custom-child-span"
    assert spans[0].attributes == {
        "operation": "child",
        "step": "1",
        "execution.id": "test",
    }

    assert spans[1].name == "root-span"
    assert spans[1].attributes == {"execution.id": "test"}
