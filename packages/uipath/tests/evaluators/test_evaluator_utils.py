"""Tests for evaluator_utils._call_llm_with_logging helper."""

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest

from uipath.eval.evaluators.evaluator_utils import _call_llm_with_logging
from uipath.eval.models.models import UiPathEvaluationError

LOGGER_NAME = "uipath.eval.evaluators.evaluator_utils"


def _make_request_data() -> dict[str, Any]:
    """Create minimal request_data for tests."""
    return {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [],
        "tool_choice": MagicMock(model_dump=lambda: {"type": "required"}),
    }


class TestCallLlmWithLogging:
    """Tests for _call_llm_with_logging."""

    @pytest.mark.asyncio
    async def test_success_returns_response(self) -> None:
        """Test that a successful LLM call returns the response unchanged."""
        expected_response = MagicMock()

        async def mock_llm_service(**kwargs: Any) -> Any:
            return expected_response

        result = await _call_llm_with_logging(
            mock_llm_service, _make_request_data(), "gpt-4o"
        )
        assert result is expected_response

    @pytest.mark.asyncio
    async def test_passes_request_data_to_llm_service(self) -> None:
        """Test that request_data kwargs are forwarded to the LLM service."""
        captured_kwargs: dict[str, Any] = {}

        async def mock_llm_service(**kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            return MagicMock()

        request_data = _make_request_data()
        request_data["temperature"] = 0.5

        await _call_llm_with_logging(mock_llm_service, request_data, "gpt-4o")
        assert captured_kwargs["model"] == "gpt-4o"
        assert captured_kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_plain_exception_wraps_in_evaluation_error(self) -> None:
        """Test that a plain exception is wrapped in UiPathEvaluationError."""

        async def mock_llm_service(**kwargs: Any) -> Any:
            raise RuntimeError("connection refused")

        with pytest.raises(UiPathEvaluationError) as exc_info:
            await _call_llm_with_logging(
                mock_llm_service, _make_request_data(), "gpt-4o"
            )

        error = exc_info.value
        assert error.error_info.code == "Python.FAILED_TO_GET_LLM_RESPONSE"
        assert "gpt-4o" in error.error_info.detail
        assert "RuntimeError" in error.error_info.detail
        assert "connection refused" in error.error_info.detail
        assert isinstance(error.__cause__, RuntimeError)

    @pytest.mark.asyncio
    async def test_http_error_includes_status_in_logs(self) -> None:
        """Test that an exception with .response logs HTTP status code and body."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "rate limited"}

        async def mock_llm_service(**kwargs: Any) -> Any:
            exc = Exception("Too Many Requests")
            exc.response = mock_response  # type: ignore[attr-defined]
            raise exc

        logger = logging.getLogger(LOGGER_NAME)
        logged_messages: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: logged_messages.append(record.getMessage())  # type: ignore[assignment]
        logger.addHandler(handler)

        try:
            with pytest.raises(UiPathEvaluationError):
                await _call_llm_with_logging(
                    mock_llm_service, _make_request_data(), "gpt-4o"
                )
        finally:
            logger.removeHandler(handler)

        all_logs = "\n".join(logged_messages)
        assert "429" in all_logs
        assert "rate limited" in all_logs

    @pytest.mark.asyncio
    async def test_http_error_json_parse_failure_falls_back_to_content(self) -> None:
        """Test fallback to .content when .json() raises."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("not json")
        mock_response.content = b"Internal Server Error"

        async def mock_llm_service(**kwargs: Any) -> Any:
            exc = Exception("Server Error")
            exc.response = mock_response  # type: ignore[attr-defined]
            raise exc

        logger = logging.getLogger(LOGGER_NAME)
        logged_messages: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: logged_messages.append(record.getMessage())  # type: ignore[assignment]
        logger.addHandler(handler)

        try:
            with pytest.raises(UiPathEvaluationError):
                await _call_llm_with_logging(
                    mock_llm_service, _make_request_data(), "gpt-4o"
                )
        finally:
            logger.removeHandler(handler)

        all_logs = "\n".join(logged_messages)
        assert "Internal Server Error" in all_logs
