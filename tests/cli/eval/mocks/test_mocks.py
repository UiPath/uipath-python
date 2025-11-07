from typing import Any
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_httpx import HTTPXMock

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    LLMMockingStrategy,
    MockitoMockingStrategy,
)
from uipath._cli._evals.mocks.cache_manager import CacheManager
from uipath._cli._evals.mocks.mocker import UiPathMockResponseGenerationError
from uipath._cli._evals.mocks.mocks import set_execution_context
from uipath.eval.mocks import mockable

_mock_span_collector = MagicMock()


def test_mockito_mockable_sync():
    # Arrange
    @mockable()
    def foo(*args, **kwargs):
        raise NotImplementedError()

    @mockable()
    def foofoo(*args, **kwargs):
        raise NotImplementedError()

    evaluation_item: dict[str, Any] = {
        "id": "evaluation-id",
        "name": "Mock foo",
        "inputs": {},
        "evaluationCriterias": {
            "ExactMatchEvaluator": None,
        },
        "mockingStrategy": {
            "type": "mockito",
            "behaviors": [
                {
                    "function": "foo",
                    "arguments": {"args": [], "kwargs": {}},
                    "then": [
                        {"type": "return", "value": "bar1"},
                        {"type": "return", "value": "bar2"},
                    ],
                }
            ],
        },
    }
    evaluation = EvaluationItem(**evaluation_item)
    assert isinstance(evaluation.mocking_strategy, MockitoMockingStrategy)

    # Act & Assert
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")
    assert foo() == "bar1"
    assert foo() == "bar2"
    assert foo() == "bar2"

    with pytest.raises(UiPathMockResponseGenerationError):
        assert foo(x=1)

    with pytest.raises(NotImplementedError):
        assert foofoo()

    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {"x": 1}
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")
    assert foo(x=1) == "bar1"

    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {
        "x": {"_target_": "mockito.any"}
    }
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")
    assert foo(x=2) == "bar1"


@pytest.mark.asyncio
async def test_mockito_mockable_async():
    # Arrange
    @mockable()
    async def foo(*args, **kwargs):
        raise NotImplementedError()

    @mockable()
    async def foofoo(*args, **kwargs):
        raise NotImplementedError()

    evaluation_item: dict[str, Any] = {
        "id": "evaluation-id",
        "name": "Mock foo",
        "inputs": {},
        "evaluationCriterias": {
            "ExactMatchEvaluator": None,
        },
        "mockingStrategy": {
            "type": "mockito",
            "behaviors": [
                {
                    "function": "foo",
                    "arguments": {"args": [], "kwargs": {}},
                    "then": [
                        {"type": "return", "value": "bar1"},
                        {"type": "return", "value": "bar2"},
                    ],
                }
            ],
        },
    }
    evaluation = EvaluationItem(**evaluation_item)
    assert isinstance(evaluation.mocking_strategy, MockitoMockingStrategy)

    # Act & Assert
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")
    assert await foo() == "bar1"
    assert await foo() == "bar2"
    assert await foo() == "bar2"

    with pytest.raises(UiPathMockResponseGenerationError):
        assert await foo(x=1)

    with pytest.raises(NotImplementedError):
        assert await foofoo()

    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {"x": 1}
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")
    assert await foo(x=1) == "bar1"

    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {
        "x": {"_target_": "mockito.any"}
    }
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")
    assert await foo(x=2) == "bar1"


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_llm_mockable_sync(httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    # Arrange
    @mockable()
    def foo(*args, **kwargs):
        raise NotImplementedError()

    @mockable()
    def foofoo(*args, **kwargs):
        raise NotImplementedError()

    evaluation_item: dict[str, Any] = {
        "id": "evaluation-id",
        "name": "Mock foo",
        "inputs": {},
        "evaluationCriterias": {
            "ExactMatchEvaluator": None,
        },
        "mockingStrategy": {
            "type": "llm",
            "prompt": "response is 'bar1'",
            "toolsToSimulate": [{"name": "foo"}],
        },
    }
    evaluation = EvaluationItem(**evaluation_item)
    assert isinstance(evaluation.mocking_strategy, LLMMockingStrategy)
    httpx_mock.add_response(
        url="https://example.com/agenthub_/llm/api/capabilities",
        status_code=200,
        json={},
    )
    httpx_mock.add_response(
        url="https://example.com/orchestrator_/llm/api/capabilities",
        status_code=200,
        json={},
    )

    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        status_code=200,
        json={
            "id": "response-id",
            "object": "",
            "created": 0,
            "model": "model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "ai",
                        "content": '{"response": "bar1"}',
                        "tool_calls": None,
                    },
                    "finish_reason": "EOS",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        },
    )
    # Act & Assert
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")

    assert foo() == "bar1"
    with pytest.raises(NotImplementedError):
        assert foofoo()
    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        status_code=200,
        json={},
    )
    with pytest.raises(UiPathMockResponseGenerationError):
        assert foo()


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_llm_mockable_async(httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    # Arrange
    @mockable()
    async def foo(*args, **kwargs):
        raise NotImplementedError()

    @mockable()
    async def foofoo(*args, **kwargs):
        raise NotImplementedError()

    evaluation_item: dict[str, Any] = {
        "id": "evaluation-id",
        "name": "Mock foo",
        "inputs": {},
        "evaluationCriterias": {
            "ExactMatchEvaluator": None,
        },
        "mockingStrategy": {
            "type": "llm",
            "prompt": "response is 'bar1'",
            "toolsToSimulate": [{"name": "foo"}],
        },
    }
    evaluation = EvaluationItem(**evaluation_item)
    assert isinstance(evaluation.mocking_strategy, LLMMockingStrategy)

    # Mock capability checks
    httpx_mock.add_response(
        url="https://example.com/agenthub_/llm/api/capabilities",
        status_code=200,
        json={},
    )
    httpx_mock.add_response(
        url="https://example.com/orchestrator_/llm/api/capabilities",
        status_code=200,
        json={},
    )

    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        status_code=200,
        json={
            "id": "response-id",
            "object": "",
            "created": 0,
            "model": "model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "ai",
                        "content": '{"response": "bar1"}',
                        "tool_calls": None,
                    },
                    "finish_reason": "EOS",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        },
    )
    # Act & Assert
    set_execution_context(evaluation, _mock_span_collector, "test-execution-id")

    assert await foo() == "bar1"
    with pytest.raises(NotImplementedError):
        assert await foofoo()

    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        status_code=200,
        json={},
    )
    with pytest.raises(UiPathMockResponseGenerationError):
        assert await foo()
