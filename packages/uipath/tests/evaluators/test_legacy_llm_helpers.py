"""Tests for legacy LLM helper functions (submit_evaluation tool-call parsing)."""

from types import SimpleNamespace
from typing import Any

import pytest

from uipath.eval.evaluators.legacy_llm_helpers import extract_tool_call_response


def _make_response(arguments: dict[str, Any]) -> Any:
    """Build a minimal chat-completions response carrying a submit_evaluation tool call."""
    tool_call = SimpleNamespace(arguments=arguments)
    message = SimpleNamespace(tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


class TestExtractToolCallResponse:
    """Test extract_tool_call_response score validation."""

    def test_valid_score_passes_through(self) -> None:
        response = _make_response({"score": 88, "justification": "ok"})

        result = extract_tool_call_response(response, "gemini-2.5-flash")

        assert result.score == 88.0
        assert result.justification == "ok"

    def test_out_of_range_score_is_rejected(self) -> None:
        # Real payload observed in production: gemini-2.5-flash returned
        # score=989898 in its submit_evaluation tool call while the justification
        # said the outputs "match perfectly". Unvalidated, this single value blew
        # a 64-item run-level average up to 15559.13%. The evaluation must surface
        # as an error rather than record a fabricated score.
        response = _make_response(
            {"score": 989898, "justification": "matches perfectly"}
        )

        with pytest.raises(ValueError, match="Invalid score 989898"):
            extract_tool_call_response(response, "gemini-2.5-flash")

    def test_out_of_range_950_is_rejected(self) -> None:
        # Second production occurrence from the same eval run: score=950
        # (the model most likely intended 95).
        response = _make_response({"score": 950, "justification": "equivalent"})

        with pytest.raises(ValueError, match="Invalid score 950"):
            extract_tool_call_response(response, "gemini-2.5-flash")

    def test_negative_score_is_rejected(self) -> None:
        response = _make_response({"score": -5, "justification": "bad"})

        with pytest.raises(ValueError, match="Invalid score -5"):
            extract_tool_call_response(response, "gpt-4o")

    @pytest.mark.parametrize("boundary", [0, 100])
    def test_boundary_scores_accepted(self, boundary: int) -> None:
        response = _make_response({"score": boundary, "justification": "j"})

        result = extract_tool_call_response(response, "m")

        assert result.score == float(boundary)
        assert result.justification == "j"

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_score_is_rejected(self, value: float) -> None:
        response = _make_response({"score": value, "justification": "j"})

        with pytest.raises(ValueError, match="Invalid score"):
            extract_tool_call_response(response, "m")

    def test_missing_score_raises(self) -> None:
        response = _make_response({"justification": "j"})

        with pytest.raises(ValueError, match="Missing 'score'"):
            extract_tool_call_response(response, "m")

    @pytest.mark.parametrize("value", ["not-a-number", None, [95]])
    def test_non_numeric_score_is_rejected(self, value: Any) -> None:
        response = _make_response({"score": value, "justification": "j"})

        with pytest.raises(ValueError, match="Non-numeric score"):
            extract_tool_call_response(response, "m")
