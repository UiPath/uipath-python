from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_httpx import HTTPXMock

from uipath.eval.mocks._cache_manager import CacheManager
from uipath.eval.mocks._input_mocker import generate_llm_input
from uipath.eval.mocks._types import InputMockingStrategy, ModelSettings
from uipath.eval.models.evaluation_set import (
    EvaluationItem,
)


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_generate_llm_input_with_model_settings(
    httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    evaluation_item: dict[str, Any] = {
        "id": "test-eval-id",
        "name": "Test Input Generation",
        "inputs": {},
        "evaluationCriterias": {"Default Evaluator": {"result": 35}},
        "expectedAgentBehavior": "Agent should multiply the numbers",
        "inputMockingStrategy": {
            "prompt": "Generate a multiplication query with 5 and 7",
            "model": {
                "model": "gpt-4o-mini-2024-07-18",
                "temperature": 0.5,
                "maxTokens": 150,
            },
        },
        "evalSetId": "test-eval-set-id",
        "createdAt": "2025-09-04T18:54:58.378Z",
        "updatedAt": "2025-09-04T18:55:55.416Z",
    }
    eval_item = EvaluationItem(**evaluation_item)

    assert isinstance(eval_item.input_mocking_strategy, InputMockingStrategy)
    assert isinstance(eval_item.input_mocking_strategy.model, ModelSettings)
    assert eval_item.input_mocking_strategy.model.model == "gpt-4o-mini-2024-07-18"
    assert eval_item.input_mocking_strategy.model.temperature == 0.5
    assert eval_item.input_mocking_strategy.model.max_tokens == 150

    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

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

    # Chat completions consults discovery to learn which parameters the model accepts.
    httpx_mock.add_response(
        url="https://example.com/llm/api/discovery",
        status_code=200,
        json=[{"modelName": "gpt-4o-mini-2024-07-18", "modelDetails": {}}],
    )

    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        status_code=200,
        json={
            "role": "assistant",
            "id": "response-id",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": '{"query": "Calculate 5 times 7"}',
                        "tool_calls": None,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        },
    )

    result = await generate_llm_input(
        eval_item.input_mocking_strategy,
        input_schema,
        expected_behavior=eval_item.expected_agent_behavior,
        expected_output={"result": 35},
    )

    # Verify the mocked input is correct
    assert result == {"query": "Calculate 5 times 7"}

    requests = httpx_mock.get_requests()
    chat_completion_requests = [r for r in requests if "chat/completions" in str(r.url)]
    assert len(chat_completion_requests) == 1, (
        "Expected exactly one chat completion request"
    )

    # OpenAI returns content via response_format; no tool-call fallback needed.
    import json

    body = json.loads(chat_completion_requests[0].content.decode("utf-8"))
    assert "response_format" in body
    assert "tools" not in body


# --- non-object results are rejected with an actionable error (SRE-655743) --


@pytest.mark.asyncio
async def test_generate_llm_input_rejects_non_object_result(monkeypatch: MonkeyPatch):
    from uipath.eval.mocks import _input_mocker
    from uipath.eval.mocks._mocker import UiPathInputMockingError

    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)

    cache_writes: list[Any] = []
    monkeypatch.setattr(
        CacheManager, "set", lambda *args, **kwargs: cache_writes.append(kwargs)
    )

    async def _fake_structured_output(*args: Any, **kwargs: Any) -> Any:
        # A non-JSON string under an object schema cannot be coerced upstream.
        return "I can't generate that input."

    monkeypatch.setattr(
        _input_mocker, "generate_structured_output", _fake_structured_output
    )

    strategy = InputMockingStrategy(
        prompt="Generate a query", model=ModelSettings(model="gpt-4o-mini-2024-07-18")
    )

    with pytest.raises(UiPathInputMockingError) as exc_info:
        await generate_llm_input(
            strategy,
            {"type": "object", "properties": {"query": {"type": "string"}}},
            expected_behavior="",
            expected_output={},
        )

    message = str(exc_info.value)
    assert "must be a JSON object" in message
    assert "str" in message
    assert "I can't generate that input." in message
    # A bad value must never be written to the cache.
    assert cache_writes == []


@pytest.mark.asyncio
async def test_generate_llm_input_unwraps_stale_stringified_cached_result(
    monkeypatch: MonkeyPatch,
):
    from uipath.eval.mocks import _input_mocker
    from uipath.eval.mocks._mock_context import cache_manager_context

    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
    # Simulate a stale cache entry written before stringified objects were
    # unwrapped. The cache is only consulted when a manager is bound to the
    # context, and a hit must be coerced the same way a fresh response is.
    monkeypatch.setattr(
        CacheManager, "get", lambda *args, **kwargs: '{"query": "cached"}'
    )
    cache_writes: list[Any] = []
    monkeypatch.setattr(
        CacheManager, "set", lambda *args, **kwargs: cache_writes.append(kwargs)
    )

    async def _unexpected_llm_call(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("cache hit must not trigger an LLM call")

    monkeypatch.setattr(
        _input_mocker, "generate_structured_output", _unexpected_llm_call
    )

    strategy = InputMockingStrategy(
        prompt="Generate a query", model=ModelSettings(model="gpt-4o-mini-2024-07-18")
    )

    token = cache_manager_context.set(CacheManager())
    try:
        result = await generate_llm_input(
            strategy,
            {"type": "object", "properties": {"query": {"type": "string"}}},
            expected_behavior="",
            expected_output={},
        )
    finally:
        cache_manager_context.reset(token)

    assert result == {"query": "cached"}
    # The healed value is written back so the stale entry is fixed on flush.
    assert [w["response"] for w in cache_writes] == [{"query": "cached"}]


@pytest.mark.asyncio
async def test_generate_llm_input_regenerates_when_cached_result_is_not_an_object(
    monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    from uipath.eval.mocks import _input_mocker
    from uipath.eval.mocks._mock_context import cache_manager_context

    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
    # A cached value that cannot be coerced to an object can never be replayed,
    # so it must be ignored and overwritten rather than failing on every run.
    monkeypatch.setattr(
        CacheManager, "get", lambda *args, **kwargs: "I can't generate that input."
    )
    cache_writes: list[Any] = []
    monkeypatch.setattr(
        CacheManager, "set", lambda *args, **kwargs: cache_writes.append(kwargs)
    )

    async def _fake_structured_output(*args: Any, **kwargs: Any) -> Any:
        return {"query": "regenerated"}

    monkeypatch.setattr(
        _input_mocker, "generate_structured_output", _fake_structured_output
    )

    strategy = InputMockingStrategy(
        prompt="Generate a query", model=ModelSettings(model="gpt-4o-mini-2024-07-18")
    )

    token = cache_manager_context.set(CacheManager())
    try:
        with caplog.at_level("WARNING", logger="uipath.eval.mocks._input_mocker"):
            result = await generate_llm_input(
                strategy,
                {"type": "object", "properties": {"query": {"type": "string"}}},
                expected_behavior="",
                expected_output={},
            )
    finally:
        cache_manager_context.reset(token)

    assert result == {"query": "regenerated"}
    assert [w["response"] for w in cache_writes] == [{"query": "regenerated"}]
    assert any(
        "Ignoring cached simulated input" in record.getMessage()
        for record in caplog.records
    )
