import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pydantic import BaseModel
from pytest_httpx import HTTPXMock

from uipath.eval.mocks import mockable
from uipath.eval.mocks._cache_manager import CacheManager
from uipath.eval.mocks._mock_context import (
    _normalize_tool_name,
    is_tool_simulated,
)
from uipath.eval.mocks._mock_runtime import (
    clear_execution_context,
    set_execution_context,
)
from uipath.eval.mocks._mocker import UiPathMockResponseGenerationError
from uipath.eval.mocks._types import (
    LLMMockingStrategy,
    MockingContext,
    MockitoMockingStrategy,
    ToolSimulation,
)
from uipath.eval.models.evaluation_set import (
    EvaluationItem,
)

_mock_span_collector = MagicMock()


class TestSetExecutionContext:
    """Tests for the set_execution_context function."""

    def test_sets_mocker_to_none_when_context_is_none(self):
        clear_execution_context()
        set_execution_context(None, _mock_span_collector, "test-execution-id")
        # Verify mocker context is None by checking is_tool_simulated returns False
        assert is_tool_simulated("any_tool") is False
        clear_execution_context()

    def test_sets_mocker_to_none_when_strategy_is_none(self):
        clear_execution_context()
        context = MockingContext(
            strategy=None,
            name="test",
            inputs={},
        )
        set_execution_context(context, _mock_span_collector, "test-execution-id")
        # Verify mocker context is None by checking is_tool_simulated returns False
        assert is_tool_simulated("any_tool") is False
        clear_execution_context()

    def test_creates_mocker_when_context_and_strategy_exist(self):
        clear_execution_context()
        context = MockingContext(
            strategy=LLMMockingStrategy(
                prompt="test prompt",
                tools_to_simulate=[ToolSimulation(name="test_tool")],
            ),
            name="test",
            inputs={},
        )
        set_execution_context(context, _mock_span_collector, "test-execution-id")
        # Verify mocker context was created by checking is_tool_simulated returns True
        assert is_tool_simulated("test_tool") is True
        clear_execution_context()


class TestNormalizeToolName:
    """Tests for the _normalize_tool_name helper function."""

    def test_replaces_underscores_with_spaces(self):
        assert _normalize_tool_name("my_tool_name") == "my tool name"

    def test_handles_no_underscores(self):
        assert _normalize_tool_name("mytool") == "mytool"

    def test_handles_empty_string(self):
        assert _normalize_tool_name("") == ""

    def test_handles_multiple_consecutive_underscores(self):
        assert _normalize_tool_name("my__tool") == "my  tool"

    def test_handles_leading_and_trailing_underscores(self):
        assert _normalize_tool_name("_tool_") == " tool "


class TestIsToolSimulated:
    """Tests for the is_tool_simulated function."""

    def test_returns_false_when_no_evaluation_context(self):
        clear_execution_context()
        assert is_tool_simulated("any_tool") is False

    def test_returns_false_when_mocking_strategy_is_none(self):
        clear_execution_context()
        evaluation_item: dict[str, Any] = {
            "id": "evaluation-id",
            "name": "Test evaluation",
            "inputs": {},
            "evaluationCriterias": {"ExactMatchEvaluator": None},
            "mockingStrategy": None,
        }
        evaluation = EvaluationItem(**evaluation_item)
        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        assert is_tool_simulated("any_tool") is False
        clear_execution_context()

    def test_returns_true_for_llm_strategy_simulated_tool(self):
        clear_execution_context()
        evaluation_item: dict[str, Any] = {
            "id": "evaluation-id",
            "name": "Test evaluation",
            "inputs": {},
            "evaluationCriterias": {"ExactMatchEvaluator": None},
            "mockingStrategy": {
                "type": "llm",
                "prompt": "test prompt",
                "toolsToSimulate": [{"name": "my_tool"}, {"name": "other_tool"}],
            },
        }
        evaluation = EvaluationItem(**evaluation_item)
        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        assert is_tool_simulated("my_tool") is True
        assert is_tool_simulated("other_tool") is True
        clear_execution_context()

    def test_returns_false_for_llm_strategy_non_simulated_tool(self):
        clear_execution_context()
        evaluation_item: dict[str, Any] = {
            "id": "evaluation-id",
            "name": "Test evaluation",
            "inputs": {},
            "evaluationCriterias": {"ExactMatchEvaluator": None},
            "mockingStrategy": {
                "type": "llm",
                "prompt": "test prompt",
                "toolsToSimulate": [{"name": "my_tool"}],
            },
        }
        evaluation = EvaluationItem(**evaluation_item)
        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        assert is_tool_simulated("not_simulated_tool") is False
        clear_execution_context()

    def test_returns_true_for_mockito_strategy_simulated_tool(self):
        clear_execution_context()
        evaluation_item: dict[str, Any] = {
            "id": "evaluation-id",
            "name": "Test evaluation",
            "inputs": {},
            "evaluationCriterias": {"ExactMatchEvaluator": None},
            "mockingStrategy": {
                "type": "mockito",
                "behaviors": [
                    {
                        "function": "my_tool",
                        "arguments": {"args": [], "kwargs": {}},
                        "then": [{"type": "return", "value": "result"}],
                    }
                ],
            },
        }
        evaluation = EvaluationItem(**evaluation_item)
        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        assert is_tool_simulated("my_tool") is True
        clear_execution_context()

    def test_returns_false_for_mockito_strategy_non_simulated_tool(self):
        clear_execution_context()
        evaluation_item: dict[str, Any] = {
            "id": "evaluation-id",
            "name": "Test evaluation",
            "inputs": {},
            "evaluationCriterias": {"ExactMatchEvaluator": None},
            "mockingStrategy": {
                "type": "mockito",
                "behaviors": [
                    {
                        "function": "my_tool",
                        "arguments": {"args": [], "kwargs": {}},
                        "then": [{"type": "return", "value": "result"}],
                    }
                ],
            },
        }
        evaluation = EvaluationItem(**evaluation_item)
        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        assert is_tool_simulated("not_simulated_tool") is False
        clear_execution_context()

    def test_handles_underscore_space_normalization_llm(self):
        """Tool names with underscores should match config with spaces."""
        clear_execution_context()
        evaluation_item: dict[str, Any] = {
            "id": "evaluation-id",
            "name": "Test evaluation",
            "inputs": {},
            "evaluationCriterias": {"ExactMatchEvaluator": None},
            "mockingStrategy": {
                "type": "llm",
                "prompt": "test prompt",
                "toolsToSimulate": [{"name": "my tool"}],
            },
        }
        evaluation = EvaluationItem(**evaluation_item)
        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        assert is_tool_simulated("my_tool") is True
        clear_execution_context()

    def test_handles_underscore_space_normalization_mockito(self):
        """Tool names with underscores should match config with spaces."""
        clear_execution_context()
        evaluation_item: dict[str, Any] = {
            "id": "evaluation-id",
            "name": "Test evaluation",
            "inputs": {},
            "evaluationCriterias": {"ExactMatchEvaluator": None},
            "mockingStrategy": {
                "type": "mockito",
                "behaviors": [
                    {
                        "function": "my tool",
                        "arguments": {"args": [], "kwargs": {}},
                        "then": [{"type": "return", "value": "result"}],
                    }
                ],
            },
        }
        evaluation = EvaluationItem(**evaluation_item)
        set_execution_context(
            MockingContext(
                strategy=evaluation.mocking_strategy,
                name=evaluation.name,
                inputs=evaluation.inputs,
            ),
            _mock_span_collector,
            "test-execution-id",
        )

        assert is_tool_simulated("my_tool") is True
        clear_execution_context()


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
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )
    assert foo() == "bar1"
    assert foo() == "bar2"
    assert foo() == "bar2"

    with pytest.raises(UiPathMockResponseGenerationError):
        assert foo(x=1)

    with pytest.raises(NotImplementedError):
        assert foofoo()

    assert evaluation.mocking_strategy.behaviors[0].arguments is not None
    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {"x": 1}
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )
    assert foo(x=1) == "bar1"

    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {
        "x": {"_target_": "mockito.any"}
    }
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )
    assert foo(x=2) == "bar1"


def test_mockito_mockable_sync_arguments_omitted():
    """Test that omitting 'arguments' entirely matches any call"""

    # Arrange
    @mockable()
    def bar(*args, **kwargs):
        raise NotImplementedError()

    evaluation_item: dict[str, Any] = {
        "id": "evaluation-id",
        "name": "Mock bar",
        "inputs": {},
        "evaluationCriterias": {
            "ExactMatchEvaluator": None,
        },
        "mockingStrategy": {
            "type": "mockito",
            "behaviors": [
                {
                    "function": "bar",
                    # No "arguments" field - should match any call
                    "then": [{"type": "return", "value": "mocked"}],
                }
            ],
        },
    }
    evaluation = EvaluationItem(**evaluation_item)
    assert isinstance(evaluation.mocking_strategy, MockitoMockingStrategy)
    # Verify arguments is None when omitted
    assert evaluation.mocking_strategy.behaviors[0].arguments is None

    # Act & Assert
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )

    # All these should work - match any call signature
    assert bar() == "mocked"
    assert bar(x=1) == "mocked"
    assert bar("positional") == "mocked"
    assert bar(a=1, b=2, c=3) == "mocked"
    assert bar("pos1", "pos2", key="value") == "mocked"


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
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )
    assert await foo() == "bar1"
    assert await foo() == "bar2"
    assert await foo() == "bar2"

    with pytest.raises(UiPathMockResponseGenerationError):
        assert await foo(x=1)

    with pytest.raises(NotImplementedError):
        assert await foofoo()

    assert evaluation.mocking_strategy.behaviors[0].arguments is not None
    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {"x": 1}
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )
    assert await foo(x=1) == "bar1"

    evaluation.mocking_strategy.behaviors[0].arguments.kwargs = {
        "x": {"_target_": "mockito.any"}
    }
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )
    assert await foo(x=2) == "bar1"


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_llm_mockable_sync(httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    # Arrange
    @mockable()
    def foo(*args, **kwargs) -> str:
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
                        "content": '"bar1"',
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
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )

    assert foo() == "bar1"

    mock_request = httpx_mock.get_request(method="POST")
    assert mock_request
    request = json.loads(mock_request.content.decode("utf-8"))
    assert request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "OutputSchema",
            "strict": False,
            "schema": {"type": "string"},
        },
    }

    with pytest.raises(NotImplementedError):
        assert foofoo()
    # Two empty responses: the response_format attempt and the tool-call fallback.
    for _ in range(2):
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
    async def foo(*args, **kwargs) -> str:
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
                        "content": '"bar1"',
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
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )

    assert await foo() == "bar1"

    mock_request = httpx_mock.get_request()
    assert mock_request
    request = json.loads(mock_request.content.decode("utf-8"))
    assert request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "OutputSchema",
            "strict": False,
            "schema": {"type": "string"},
        },
    }

    with pytest.raises(NotImplementedError):
        assert await foofoo()

    # Two empty responses: the response_format attempt and the tool-call fallback.
    for _ in range(2):
        httpx_mock.add_response(
            url="https://example.com/llm/api/chat/completions"
            "?api-version=2024-08-01-preview",
            status_code=200,
            json={},
        )
    with pytest.raises(UiPathMockResponseGenerationError):
        assert await foo()


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_llm_mockable_with_output_schema_sync(
    httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    class ToolResponseMock(BaseModel):
        content: str

    # Arrange
    @mockable(output_schema=ToolResponseMock.model_json_schema())
    def foo(*args, **kwargs) -> dict[str, Any]:
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
            "prompt": "response content is 'bar1'",
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
                        "content": '{"content": "bar1"}',
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
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )

    assert foo() == {"content": "bar1"}
    mock_request = httpx_mock.get_request()
    assert mock_request
    request = json.loads(mock_request.content.decode("utf-8"))
    assert request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "OutputSchema",
            "strict": False,
            "schema": {
                "required": ["content"],
                "type": "object",
                "additionalProperties": False,
                "properties": {"content": {"type": "string"}},
            },
        },
    }


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_llm_mockable_with_output_schema_async(
    httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    class ToolResponseMock(BaseModel):
        content: str

    # Arrange
    @mockable(output_schema=ToolResponseMock.model_json_schema())
    async def foo(*args, **kwargs) -> dict[str, Any]:
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
            "prompt": "response content is 'bar1'",
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
                        "content": '{"content": "bar1"}',
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
    set_execution_context(
        MockingContext(
            strategy=evaluation.mocking_strategy,
            name=evaluation.name,
            inputs=evaluation.inputs,
        ),
        _mock_span_collector,
        "test-execution-id",
    )

    assert await foo() == {"content": "bar1"}
    mock_request = httpx_mock.get_request()
    assert mock_request
    request = json.loads(mock_request.content.decode("utf-8"))
    assert request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "OutputSchema",
            "strict": False,
            "schema": {
                "required": ["content"],
                "type": "object",
                "additionalProperties": False,
                "properties": {"content": {"type": "string"}},
            },
        },
    }


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_llm_mockable_falls_back_to_tool_call_for_non_openai(
    httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
):
    """Tool simulation works for non-OpenAI providers (AE-1646).

    Non-OpenAI providers (Claude/Bedrock, Gemini) return ``response_format``
    requests with empty ``content``. The mocker must then fall back to function
    calling and read the result from the forced tool call's arguments.
    """
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    @mockable()
    async def foo(*args, **kwargs) -> str:
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
            "model": {"model": "anthropic.claude-sonnet-4-5-20250929-v1:0"},
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

    def _completion(message: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": "response-id",
            "object": "",
            "created": 0,
            "model": "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    # First call (response_format) returns empty content — the non-OpenAI failure.
    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        status_code=200,
        json=_completion({"role": "assistant", "content": None, "tool_calls": None}),
    )
    # Fallback call (function calling) returns the structured result.
    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        status_code=200,
        json=_completion(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "submit_tool_response",
                        "arguments": {"response": "bar1"},
                    }
                ],
            }
        ),
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

    assert await foo() == "bar1"

    requests = [
        r for r in httpx_mock.get_requests() if "chat/completions" in str(r.url)
    ]
    assert len(requests) == 2
    first = json.loads(requests[0].content.decode("utf-8"))
    second = json.loads(requests[1].content.decode("utf-8"))
    # First attempt uses response_format; fallback uses a forced tool call.
    assert "response_format" in first
    assert "tools" not in first
    assert second["tool_choice"] == {"type": "required"}
    assert second["tools"][0]["name"] == "submit_tool_response"
    assert "response_format" not in second


class TestUiPathMockRuntime:
    """Tests for UiPathMockRuntime execute/stream/get_schema paths."""

    def _make_context(self) -> MockingContext:
        return MockingContext(
            strategy=LLMMockingStrategy(
                prompt="test",
                tools_to_simulate=[ToolSimulation(name="my_tool")],
            ),
            name="test",
            inputs={},
        )

    async def test_execute_with_mocking_context_sets_and_clears(self):
        from unittest.mock import AsyncMock, patch

        from uipath.eval.mocks._mock_runtime import UiPathMockRuntime

        delegate = MagicMock()
        mock_result = MagicMock()
        delegate.execute = AsyncMock(return_value=mock_result)

        runtime = UiPathMockRuntime(
            delegate=delegate,
            mocking_context=self._make_context(),
        )

        with (
            patch("uipath.eval.mocks._mock_runtime.set_execution_context") as mock_set,
            patch(
                "uipath.eval.mocks._mock_runtime.clear_execution_context"
            ) as mock_clear,
        ):
            result = await runtime.execute({"key": "value"})

        assert result is mock_result
        mock_set.assert_called_once()
        mock_clear.assert_called_once()

    async def test_stream_with_mocking_context_sets_and_clears(self):
        from unittest.mock import patch

        from uipath.eval.mocks._mock_runtime import UiPathMockRuntime

        sentinel = object()

        async def _gen(*args, **kwargs):
            yield sentinel

        delegate = MagicMock()
        delegate.stream = _gen

        runtime = UiPathMockRuntime(
            delegate=delegate,
            mocking_context=self._make_context(),
        )

        with (
            patch("uipath.eval.mocks._mock_runtime.set_execution_context") as mock_set,
            patch(
                "uipath.eval.mocks._mock_runtime.clear_execution_context"
            ) as mock_clear,
        ):
            events = [e async for e in runtime.stream({})]

        assert events == [sentinel]
        mock_set.assert_called_once()
        mock_clear.assert_called_once()

    async def test_stream_without_mocking_context_passes_through(self):
        from unittest.mock import patch

        from uipath.eval.mocks._mock_runtime import UiPathMockRuntime

        sentinel = object()

        async def _gen(*args, **kwargs):
            yield sentinel

        delegate = MagicMock()
        delegate.stream = _gen

        runtime = UiPathMockRuntime(delegate=delegate, mocking_context=None)
        with patch(
            "uipath.eval.mocks._mock_runtime.load_simulation_config", return_value=None
        ):
            runtime._mocking_context = None
            events = [e async for e in runtime.stream({})]

        assert events == [sentinel]

    async def test_get_schema_delegates(self):
        from unittest.mock import AsyncMock, patch

        from uipath.eval.mocks._mock_runtime import UiPathMockRuntime

        schema = MagicMock()
        delegate = MagicMock()
        delegate.get_schema = AsyncMock(return_value=schema)

        runtime = UiPathMockRuntime(delegate=delegate, mocking_context=None)
        with patch(
            "uipath.eval.mocks._mock_runtime.load_simulation_config", return_value=None
        ):
            result = await runtime.get_schema()

        assert result is schema

    def test_set_execution_context_handles_mocker_creation_failure(self):
        from unittest.mock import patch

        from uipath.eval._execution_context import ExecutionSpanCollector
        from uipath.eval.mocks._mock_context import mocker_context
        from uipath.eval.mocks._mock_runtime import set_execution_context

        context = self._make_context()
        with patch(
            "uipath.eval.mocks._mock_runtime.MockerFactory.create",
            side_effect=RuntimeError("boom"),
        ):
            set_execution_context(context, ExecutionSpanCollector(), "test-id")

        # mocking_context is set, but mocker_context must be None on failure
        assert mocker_context.get() is None
        clear_execution_context()
