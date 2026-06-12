"""Regression tests: @mockable must not collide with user args named `func`/`params`."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from uipath.eval.mocks import mockable
from uipath.eval.mocks._mock_runtime import (
    clear_execution_context,
    set_execution_context,
)
from uipath.eval.mocks._types import MockingContext
from uipath.eval.models.evaluation_set import EvaluationItem

_mock_span_collector = MagicMock()


def _build_evaluation(
    function_name: str, kwargs: dict[str, Any], value: Any
) -> EvaluationItem:
    evaluation_item: dict[str, Any] = {
        "id": "evaluation-id",
        "name": "Test evaluation",
        "inputs": {},
        "evaluationCriterias": {"ExactMatchEvaluator": None},
        "mockingStrategy": {
            "type": "mockito",
            "behaviors": [
                {
                    "function": function_name,
                    "arguments": {"args": [], "kwargs": kwargs},
                    "then": [{"type": "return", "value": value}],
                }
            ],
        },
    }
    return EvaluationItem(**evaluation_item)


class TestMockableArgCollision:
    """Ensure `@mockable` works when the wrapped function has args named `func` or `params`."""

    def test_sync_function_with_func_and_params_args(self):
        """A sync mockable function that takes `func` and `params` kwargs should not raise."""

        @mockable()
        def test_function(func: str, params: dict[str, Any]) -> str:
            raise NotImplementedError()

        evaluation = _build_evaluation(
            "test_function",
            kwargs={"func": "some_func", "params": {"k": "v"}},
            value="mocked_result",
        )

        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        try:
            with patch("uipath.eval.mocks.mockable.UiPathSpanUtils"):
                with patch("uipath.eval.mocks.mockable.trace"):
                    result = test_function(func="some_func", params={"k": "v"})

            assert result == "mocked_result"
        finally:
            clear_execution_context()

    @pytest.mark.asyncio
    async def test_async_function_with_func_and_params_args(self):
        """An async mockable function that takes `func` and `params` kwargs should not raise."""

        @mockable()
        async def test_function(func: str, params: dict[str, Any]) -> str:
            raise NotImplementedError()

        evaluation = _build_evaluation(
            "test_function",
            kwargs={"func": "some_func", "params": {"k": "v"}},
            value="mocked_result",
        )

        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        try:
            with patch("uipath.eval.mocks.mockable.UiPathSpanUtils"):
                with patch("uipath.eval.mocks.mockable.trace"):
                    result = await test_function(func="some_func", params={"k": "v"})

            assert result == "mocked_result"
        finally:
            clear_execution_context()
