"""Tests that the functions runtime correctly unwraps decorated functions."""

import textwrap

import pytest

from uipath.functions.runtime import UiPathFunctionsRuntime


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
