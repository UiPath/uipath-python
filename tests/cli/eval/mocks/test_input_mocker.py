from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_httpx import HTTPXMock

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    InputMockingStrategy,
    ModelSettings,
)
from uipath._cli._evals.mocks.cache_manager import CacheManager
from uipath._cli._evals.mocks.input_mocker import generate_llm_input


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

    result = await generate_llm_input(eval_item, input_schema)

    # Verify the mocked input is correct
    assert result == {"query": "Calculate 5 times 7"}

    requests = httpx_mock.get_requests()
    chat_completion_requests = [r for r in requests if "chat/completions" in str(r.url)]
    assert len(chat_completion_requests) == 1, (
        "Expected exactly one chat completion request"
    )
