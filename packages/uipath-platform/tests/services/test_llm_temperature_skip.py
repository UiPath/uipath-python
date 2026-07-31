"""Temperature is dropped for models that reject it, per LLM Gateway discovery.

Regression coverage for Sonnet 5 evals: the judge sent `temperature` on every
normalized chat completion, and the gateway answered 400 "`temperature` is
deprecated for this model."
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.chat import UiPathLlmChatService, UiPathOpenAIService
from uipath.platform.chat._model_capabilities import _reset_cache

SKIP_TEMPERATURE_MODEL = "anthropic.claude-sonnet-5"

SKIP_TEMPERATURE_DISCOVERY = [
    {
        "modelName": SKIP_TEMPERATURE_MODEL,
        "modelDetails": {"shouldSkipTemperature": True},
    }
]


def _discovery_response(models: list[dict[str, Any]]) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = models
    return response


def _completion_response(model: str) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return response


def _responder(discovery: list[dict[str, Any]] | Exception, model: str = "test-model"):
    """Answer by endpoint, so assertions don't depend on call ordering."""

    async def respond(_method, endpoint, **_kwargs):
        if "discovery" in str(endpoint):
            if isinstance(discovery, Exception):
                raise discovery
            return _discovery_response(discovery)
        return _completion_response(model)

    return respond


def _is_discovery(call) -> bool:
    return "discovery" in str(call.args[1])


def _discovery_calls(mock_request: MagicMock) -> list[Any]:
    return [c for c in mock_request.call_args_list if _is_discovery(c)]


def _completion_body(mock_request: MagicMock) -> dict[str, Any]:
    completions = [c for c in mock_request.call_args_list if not _is_discovery(c)]
    assert completions, "no chat completion request was sent"
    return completions[-1][1]["json"]


class TestSkipTemperatureFromDiscovery:
    @pytest.fixture(autouse=True)
    def clear_discovery_cache(self):
        # The cache is process-wide; keep it from leaking in either direction.
        _reset_cache()
        yield
        _reset_cache()

    @pytest.fixture
    def config(self):
        return UiPathApiConfig(base_url="https://example.com", secret="test_secret")

    @pytest.fixture
    def execution_context(self):
        return UiPathExecutionContext()

    @pytest.fixture
    def llm_service(self, config, execution_context):
        return UiPathLlmChatService(config=config, execution_context=execution_context)

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_omits_temperature_when_discovery_sets_flag(
        self, mock_request, llm_service
    ):
        mock_request.side_effect = _responder(
            SKIP_TEMPERATURE_DISCOVERY, SKIP_TEMPERATURE_MODEL
        )

        await llm_service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model=SKIP_TEMPERATURE_MODEL,
            temperature=0,
        )

        assert "temperature" not in _completion_body(mock_request)

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_keeps_temperature_when_flag_absent(self, mock_request, llm_service):
        mock_request.side_effect = _responder(
            [
                {
                    "modelName": "gpt-4o-2024-11-20",
                    "modelDetails": {"maxOutputTokens": 4096},
                }
            ],
            "gpt-4o-2024-11-20",
        )

        await llm_service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o-2024-11-20",
            temperature=0.3,
        )

        assert _completion_body(mock_request)["temperature"] == 0.3

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_keeps_temperature_for_model_missing_from_discovery(
        self, mock_request, llm_service
    ):
        mock_request.side_effect = _responder(
            SKIP_TEMPERATURE_DISCOVERY, "some-other-model"
        )

        await llm_service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model="some-other-model",
            temperature=0,
        )

        assert _completion_body(mock_request)["temperature"] == 0

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_keeps_temperature_when_discovery_unavailable(
        self, mock_request, llm_service
    ):
        """Discovery being down must not fail or silently alter the LLM call."""
        mock_request.side_effect = _responder(
            RuntimeError("discovery unreachable"), SKIP_TEMPERATURE_MODEL
        )

        await llm_service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model=SKIP_TEMPERATURE_MODEL,
            temperature=0,
        )

        assert _completion_body(mock_request)["temperature"] == 0

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_discovery_fetched_once_for_repeated_calls(
        self, mock_request, llm_service
    ):
        mock_request.side_effect = _responder(
            SKIP_TEMPERATURE_DISCOVERY, SKIP_TEMPERATURE_MODEL
        )

        for _ in range(2):
            await llm_service.chat_completions(
                messages=[{"role": "user", "content": "Hello"}],
                model=SKIP_TEMPERATURE_MODEL,
                temperature=0,
            )

        assert len(_discovery_calls(mock_request)) == 1
        assert "temperature" not in _completion_body(mock_request)

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_discovery_scoped_by_agenthub_config(
        self, mock_request, config, execution_context
    ):
        service = UiPathLlmChatService(
            config=config,
            execution_context=execution_context,
            agenthub_config="agentsevals",
        )
        mock_request.side_effect = _responder([], SKIP_TEMPERATURE_MODEL)

        await service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model=SKIP_TEMPERATURE_MODEL,
        )

        discovery_headers = _discovery_calls(mock_request)[0][1]["headers"]
        assert discovery_headers["x-uipath-agenthub-config"] == "agentsevals"

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathOpenAIService.request_async"
    )
    @pytest.mark.asyncio
    async def test_openai_compatible_path_omits_temperature(
        self, mock_request, config, execution_context
    ):
        service = UiPathOpenAIService(
            config=config, execution_context=execution_context
        )
        mock_request.side_effect = _responder(
            SKIP_TEMPERATURE_DISCOVERY, SKIP_TEMPERATURE_MODEL
        )

        await service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model=SKIP_TEMPERATURE_MODEL,
            temperature=0,
        )

        assert "temperature" not in _completion_body(mock_request)
