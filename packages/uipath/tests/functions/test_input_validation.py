"""Tests that invalid inputs surface as classified user errors, not crashes."""

import textwrap

import pytest

from uipath.functions.runtime import UiPathFunctionsRuntime
from uipath.runtime.errors import UiPathErrorCategory, UiPathRuntimeError


@pytest.fixture
def calculator_module(tmp_path):
    """Create a module with a Pydantic-typed entrypoint."""
    (tmp_path / "calculator.py").write_text(
        textwrap.dedent("""\
        from pydantic import BaseModel


        class CalculatorInput(BaseModel):
            a: int
            b: int


        class CalculatorOutput(BaseModel):
            result: int


        async def main(input: CalculatorInput) -> CalculatorOutput:
            return CalculatorOutput(result=input.a + input.b)
        """)
    )
    return tmp_path / "calculator.py"


@pytest.mark.asyncio
async def test_valid_input_executes(calculator_module):
    """Sanity check: well-formed input still executes normally."""
    runtime = UiPathFunctionsRuntime(str(calculator_module), "main", "calculator")
    result = await runtime.execute({"a": 1, "b": 2})
    assert result.output == {"result": 3}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_input",
    [
        {"a": "hello", "b": 2},
        {"a": None, "b": 2},
        {"a": [1, 2], "b": 2},
        {"a": {"x": 1}, "b": 2},
    ],
)
async def test_invalid_input_raises_user_error(calculator_module, bad_input):
    """Schema-mismatched input yields a USER-category error without a traceback."""
    runtime = UiPathFunctionsRuntime(str(calculator_module), "main", "calculator")
    with pytest.raises(UiPathRuntimeError) as exc_info:
        await runtime.execute(bad_input)

    error_info = exc_info.value.error_info
    assert error_info.category == UiPathErrorCategory.USER
    assert error_info.code == "Python.INPUT_INVALID_JSON"
    assert error_info.title == "Invalid input"
    assert "CalculatorInput" in error_info.detail
    assert "main" in error_info.detail
    assert "Traceback" not in error_info.detail


@pytest.mark.asyncio
async def test_invalid_input_error_lists_offending_fields(calculator_module):
    """The error detail names each invalid field with the validation message."""
    runtime = UiPathFunctionsRuntime(str(calculator_module), "main", "calculator")
    with pytest.raises(UiPathRuntimeError) as exc_info:
        await runtime.execute({"a": "hello", "b": "world"})

    detail = exc_info.value.error_info.detail
    assert "a:" in detail
    assert "b:" in detail
