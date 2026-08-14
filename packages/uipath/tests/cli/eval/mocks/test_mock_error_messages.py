import asyncio
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from uipath.eval.mocks import _input_mocker
from uipath.eval.mocks._input_mocker import generate_llm_input
from uipath.eval.mocks._mocker import (
    UiPathInputMockingError,
    format_exception_message,
)
from uipath.eval.mocks._types import InputMockingStrategy


def test_format_exception_message_with_message():
    assert format_exception_message(ValueError("bad value")) == "ValueError: bad value"


def test_format_exception_message_empty_str():
    # asyncio.TimeoutError and CancelledError stringify to "" — the type name
    # must still be surfaced so the wrapped message is never blank.
    assert format_exception_message(asyncio.TimeoutError()) == "TimeoutError"
    assert format_exception_message(asyncio.CancelledError()) == "CancelledError"


def test_format_exception_message_whitespace_only():
    assert format_exception_message(RuntimeError("   ")) == "RuntimeError"


@pytest.mark.asyncio
async def test_generate_llm_input_wraps_empty_str_exception(
    monkeypatch: MonkeyPatch,
):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")

    async def raise_timeout(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.TimeoutError()

    monkeypatch.setattr(_input_mocker, "generate_structured_output", raise_timeout)

    with pytest.raises(UiPathInputMockingError) as exc_info:
        await generate_llm_input(
            mocking_strategy=InputMockingStrategy(prompt="generate something"),
            input_schema={"type": "object", "properties": {}},
            expected_behavior="",
            expected_output={},
        )

    assert str(exc_info.value) == "Failed to generate input: TimeoutError"
