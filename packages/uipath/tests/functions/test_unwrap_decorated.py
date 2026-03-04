"""Tests that the functions runtime correctly unwraps decorated functions."""

import textwrap

import pytest

from uipath.functions.runtime import UiPathFunctionsRuntime
from uipath.runtime.errors import UiPathRuntimeError
from uipath.runtime.events import UiPathRuntimeStateEvent, UiPathRuntimeStatePhase


@pytest.fixture
def decorated_module(tmp_path):
    """Create a module with a decorated function using functools.wraps."""
    (tmp_path / "decorated.py").write_text(
        textwrap.dedent("""\
        import functools
        from dataclasses import dataclass


        @dataclass
        class TreeNode:
            value: int
            left: "TreeNode | None" = None
            right: "TreeNode | None" = None


        @dataclass
        class TreeStats:
            total_nodes: int
            max_value: int


        def mock_traced(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return wrapper


        @mock_traced
        async def main(input: TreeNode) -> TreeStats:
            return TreeStats(total_nodes=1, max_value=input.value)
        """)
    )
    return tmp_path / "decorated.py"


@pytest.mark.asyncio
async def test_get_schema_unwraps_decorated_function(decorated_module):
    """get_schema should see through decorators to find the original type hints."""
    runtime = UiPathFunctionsRuntime(str(decorated_module), "main", "decorated")
    schema = await runtime.get_schema()

    # The input schema should reflect TreeNode, not be empty
    assert schema.input is not None
    props = schema.input.get("properties", {})
    assert "value" in props

    # The output schema should reflect TreeStats
    assert schema.output is not None
    out_props = schema.output.get("properties", {})
    assert "total_nodes" in out_props
    assert "max_value" in out_props


@pytest.mark.asyncio
async def test_execute_unwraps_decorated_function(decorated_module):
    """execute should unwrap the decorator to read the signature, but still call the wrapper."""
    runtime = UiPathFunctionsRuntime(str(decorated_module), "main", "decorated")
    result = await runtime.execute({"value": 42})

    assert isinstance(result.output, dict)
    assert result.output["total_nodes"] == 1
    assert result.output["max_value"] == 42


@pytest.mark.asyncio
async def test_schema_type_defaults_to_function(decorated_module):
    """Schema type should be 'function' by default."""
    runtime = UiPathFunctionsRuntime(str(decorated_module), "main", "decorated")
    schema = await runtime.get_schema()

    assert schema.type == "function"


@pytest.mark.asyncio
async def test_schema_type_reflects_entrypoint_type(decorated_module):
    """Schema type should reflect the entrypoint_type passed to the runtime."""
    runtime_fn = UiPathFunctionsRuntime(
        str(decorated_module), "main", "decorated", entrypoint_type="function"
    )
    schema_fn = await runtime_fn.get_schema()
    assert schema_fn.type == "function"

    runtime_agent = UiPathFunctionsRuntime(
        str(decorated_module), "main", "decorated", entrypoint_type="agent"
    )
    schema_agent = await runtime_agent.get_schema()
    assert schema_agent.type == "agent"


@pytest.fixture
def future_annotations_module(tmp_path):
    """Create a module using `from __future__ import annotations` (PEP 563)."""
    (tmp_path / "future_ann.py").write_text(
        textwrap.dedent("""\
        from __future__ import annotations

        from pydantic import BaseModel


        class OrderInput(BaseModel):
            customer_name: str
            quantity: int = 1


        class OrderOutput(BaseModel):
            accepted: bool
            total: float


        def main(order: OrderInput) -> OrderOutput:
            return OrderOutput(accepted=True, total=order.quantity * 9.99)
        """)
    )
    return tmp_path / "future_ann.py"


@pytest.mark.asyncio
async def test_execute_resolves_future_annotations(future_annotations_module):
    """PEP 563 stringified annotations should be resolved via get_type_hints."""
    runtime = UiPathFunctionsRuntime(
        str(future_annotations_module), "main", "future_ann"
    )
    result = await runtime.execute({"customer_name": "Alice", "quantity": 2})

    assert result.output == {"accepted": True, "total": 19.98}


@pytest.fixture
def failing_module(tmp_path):
    """Create a module whose function always raises."""
    (tmp_path / "failing.py").write_text(
        textwrap.dedent("""\
        def main(data: dict) -> dict:
            raise ValueError("something went wrong")
        """)
    )
    return tmp_path / "failing.py"


@pytest.mark.asyncio
async def test_execute_raises_on_function_error(failing_module):
    """Function errors should propagate as UiPathRuntimeError, not return FAULTED."""
    runtime = UiPathFunctionsRuntime(str(failing_module), "main", "failing")

    with pytest.raises(UiPathRuntimeError, match="something went wrong"):
        await runtime.execute({"key": "value"})


@pytest.mark.asyncio
async def test_stream_yields_faulted_then_raises(failing_module):
    """stream() should yield STARTED, then FAULTED, then raise UiPathRuntimeError."""
    runtime = UiPathFunctionsRuntime(str(failing_module), "main", "failing")

    events = []
    with pytest.raises(UiPathRuntimeError, match="something went wrong"):
        async for event in runtime.stream({"key": "value"}):
            events.append(event)

    assert len(events) == 2
    assert isinstance(events[0], UiPathRuntimeStateEvent)
    assert events[0].phase == UiPathRuntimeStatePhase.STARTED
    assert isinstance(events[1], UiPathRuntimeStateEvent)
    assert events[1].phase == UiPathRuntimeStatePhase.FAULTED
