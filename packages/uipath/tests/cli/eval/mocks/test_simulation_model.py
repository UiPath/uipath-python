import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_httpx import HTTPXMock

from uipath.eval.mocks import mockable
from uipath.eval.mocks._cache_manager import CacheManager
from uipath.eval.mocks._mock_runtime import (
    build_mocking_context,
    clear_execution_context,
    set_execution_context,
)
from uipath.eval.mocks._simulation_model import (
    SIMULATION_MAX_TOKENS,
    SIMULATION_MODEL_ENV,
    get_agent_max_tokens,
    simulation_completion_kwargs,
    simulation_model_settings,
)
from uipath.eval.mocks._types import (
    LLMMockingStrategy,
    MockingContext,
    ModelSettings,
    SimulationConfig,
    ToolSimulation,
)
from uipath.runtime.schema import UiPathRuntimeSchema

BYOM_MODEL = "Siemens-SDC-gpt-4o"


def test_defaults_to_gateway_model_without_settings_or_env(monkeypatch: MonkeyPatch):
    monkeypatch.delenv(SIMULATION_MODEL_ENV, raising=False)

    assert simulation_completion_kwargs(None) == {
        "model": "gpt-4.1-mini-2025-04-14",
        "max_tokens": SIMULATION_MAX_TOKENS,
    }


def test_env_model_applies_when_settings_have_no_model(monkeypatch: MonkeyPatch):
    monkeypatch.setenv(SIMULATION_MODEL_ENV, BYOM_MODEL)

    assert simulation_completion_kwargs(None) == {
        "model": BYOM_MODEL,
        "max_tokens": SIMULATION_MAX_TOKENS,
    }


def test_configured_model_wins_over_env(monkeypatch: MonkeyPatch):
    monkeypatch.setenv(SIMULATION_MODEL_ENV, BYOM_MODEL)
    settings = ModelSettings(model="gpt-4o-2024-11-20", temperature=0.2)

    assert simulation_completion_kwargs(settings) == {
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.2,
        "max_tokens": SIMULATION_MAX_TOKENS,
    }


def test_configured_max_tokens_is_kept():
    settings = ModelSettings(model="gpt-4o-2024-11-20", maxTokens=150)

    assert simulation_completion_kwargs(settings)["max_tokens"] == 150


@pytest.mark.parametrize(
    ("agent_max_tokens", "expected"),
    [
        (128000, SIMULATION_MAX_TOKENS),
        (8192, 8192),
        (None, SIMULATION_MAX_TOKENS),
        (0, SIMULATION_MAX_TOKENS),
    ],
)
def test_agent_model_settings_cap_the_agent_max_tokens(
    agent_max_tokens: int | None, expected: int
):
    settings = simulation_model_settings("gpt-6-luna", agent_max_tokens)

    assert settings.model == "gpt-6-luna"
    assert settings.max_tokens == expected


def _schema(metadata: dict[str, Any] | None) -> UiPathRuntimeSchema:
    return UiPathRuntimeSchema(
        filePath="agent.json",
        uniqueId="id",
        type="agent",
        input={},
        output={},
        metadata=metadata,
    )


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"settings": {"model": "gpt-6-luna", "max_tokens": 128000}}, 128000),
        ({"settings": {"model": "gpt-6-luna", "maxTokens": 8192}}, 8192),
        ({"settings": {"model": "gpt-6-luna", "max_tokens": 0}}, None),
        ({"settings": {"model": "gpt-6-luna", "max_tokens": "8192"}}, None),
        ({"settings": {"model": "gpt-6-luna"}}, None),
        (None, None),
    ],
)
def test_get_agent_max_tokens_reads_the_agent_settings(
    metadata: dict[str, Any] | None, expected: int | None
):
    assert get_agent_max_tokens(_schema(metadata)) == expected


def test_debug_simulation_uses_the_agent_model_and_capped_max_tokens():
    config = SimulationConfig.model_validate(
        {"enabled": True, "toolsToSimulate": [{"name": "web_search"}]}
    )

    context = build_mocking_context(config, "gpt-6-luna", 128000)

    assert context is not None
    assert isinstance(context.strategy, LLMMockingStrategy)
    assert context.strategy.model == ModelSettings(
        model="gpt-6-luna", maxTokens=SIMULATION_MAX_TOKENS
    )


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_tool_simulation_sends_env_model(
    httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
    monkeypatch.setenv(SIMULATION_MODEL_ENV, BYOM_MODEL)
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    @mockable()
    def web_search(*args, **kwargs) -> str:
        raise NotImplementedError()

    for service in ("agenthub_", "orchestrator_"):
        httpx_mock.add_response(
            url=f"https://example.com/{service}/llm/api/capabilities", json={}
        )
    httpx_mock.add_response(
        url="https://example.com/llm/api/chat/completions"
        "?api-version=2024-08-01-preview",
        json={
            "id": "response-id",
            "object": "",
            "created": 0,
            "model": BYOM_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "ai", "content": '"ok"', "tool_calls": None},
                    "finish_reason": "EOS",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
    # Mirrors what cli_run/cli_debug build for a coded agent: no model anywhere.
    set_execution_context(
        MockingContext(
            strategy=LLMMockingStrategy(
                prompt="",
                tools_to_simulate=[ToolSimulation(name="web_search")],
            ),
            name="debug-simulation",
        ),
        MagicMock(),
        "test-execution-id",
    )
    try:
        assert web_search() == "ok"
    finally:
        clear_execution_context()

    request = httpx_mock.get_request(method="POST")
    assert request is not None
    assert request.headers["X-UiPath-LlmGateway-NormalizedApi-ModelName"] == BYOM_MODEL
    assert json.loads(request.content)["max_tokens"] == SIMULATION_MAX_TOKENS
