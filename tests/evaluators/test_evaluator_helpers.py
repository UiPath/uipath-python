"""Test module for evaluator helper functions.

This module contains comprehensive tests for helper functions used by coded evaluators,
including functions for tool call extraction (`extract_tool_calls`, `extract_tool_calls_names`,
`extract_tool_calls_outputs`) and various scoring functions (`tool_calls_args_score`,
`tool_calls_count_score`, `tool_calls_order_score`, `tool_calls_output_score`).
These tests ensure consistent behavior and proper justification structures for each helper.
"""

from typing import Any

import pytest

from uipath.eval._helpers.evaluators_helpers import (
    extract_tool_calls,
    extract_tool_calls_names,
    extract_tool_calls_outputs,
    tool_calls_args_score,
    tool_calls_count_score,
    tool_calls_order_score,
    tool_calls_output_score,
)
from uipath.eval.models.models import ToolCall, ToolOutput


class TestToolCallsOrderScore:
    """Test tool_calls_order_score helper function."""

    def test_empty_both_lists(self) -> None:
        """Test when both expected and actual lists are empty."""
        score, justification = tool_calls_order_score([], [], strict=False)

        assert score == 1.0
        assert isinstance(justification, dict)
        assert "actual_tool_calls_order" in justification
        assert "expected_tool_calls_order" in justification
        assert "lcs" in justification
        assert justification["lcs"] == []

    def test_empty_actual_list(self) -> None:
        """Test when actual list is empty but expected is not."""
        score, justification = tool_calls_order_score([], ["tool1"], strict=False)

        assert score == 0.0
        assert isinstance(justification, dict)
        assert justification["actual_tool_calls_order"] == []
        assert justification["expected_tool_calls_order"] == ["tool1"]
        assert justification["lcs"] == []

    def test_empty_expected_list(self) -> None:
        """Test when expected list is empty but actual is not."""
        score, justification = tool_calls_order_score(["tool1"], [], strict=False)

        assert score == 0.0
        assert isinstance(justification, dict)
        assert justification["actual_tool_calls_order"] == ["tool1"]
        assert justification["expected_tool_calls_order"] == []
        assert justification["lcs"] == []

    def test_perfect_match_non_strict(self) -> None:
        """Test perfect match in non-strict mode."""
        actual = ["tool1", "tool2", "tool3"]
        expected = ["tool1", "tool2", "tool3"]
        score, justification = tool_calls_order_score(actual, expected, strict=False)

        assert score == 1.0
        assert justification["lcs"] == expected
        assert justification["actual_tool_calls_order"] == actual
        assert justification["expected_tool_calls_order"] == expected

    def test_perfect_match_strict(self) -> None:
        """Test perfect match in strict mode."""
        actual = ["tool1", "tool2", "tool3"]
        expected = ["tool1", "tool2", "tool3"]
        score, justification = tool_calls_order_score(actual, expected, strict=True)

        assert score == 1.0
        assert justification["lcs"] == expected

    def test_partial_match_non_strict(self) -> None:
        """Test partial match in non-strict mode (LCS calculation)."""
        actual = ["tool1", "tool3", "tool2"]
        expected = ["tool1", "tool2", "tool3"]
        score, justification = tool_calls_order_score(actual, expected, strict=False)

        # LCS should be calculated - score should be between 0 and 1
        assert 0.0 < score < 1.0
        assert len(justification["lcs"]) > 0

    def test_mismatch_strict(self) -> None:
        """Test mismatch in strict mode."""
        actual = ["tool2", "tool1"]
        expected = ["tool1", "tool2"]
        score, justification = tool_calls_order_score(actual, expected, strict=True)

        assert score == 0.0
        assert justification["lcs"] == []


class TestToolCallsCountScore:
    """Test tool_calls_count_score helper function."""

    def test_empty_both_dicts(self) -> None:
        """Test when both expected and actual dicts are empty."""
        score, justification = tool_calls_count_score({}, {}, strict=False)

        assert score == 1.0
        assert isinstance(justification, dict)
        assert "explained_tool_calls_count" in justification
        assert isinstance(justification["explained_tool_calls_count"], dict)
        assert "_result" in justification["explained_tool_calls_count"]

    def test_empty_actual_dict(self) -> None:
        """Test when actual dict is empty but expected is not."""
        expected = {"tool1": ("==", 1)}
        score, justification = tool_calls_count_score({}, expected, strict=False)

        assert score == 0.0
        assert isinstance(justification["explained_tool_calls_count"], dict)
        assert "_result" in justification["explained_tool_calls_count"]

    def test_empty_expected_dict(self) -> None:
        """Test when expected dict is empty but actual is not."""
        actual = {"tool1": 1}
        score, justification = tool_calls_count_score(actual, {}, strict=False)

        assert score == 0.0
        assert isinstance(justification["explained_tool_calls_count"], dict)
        assert "_result" in justification["explained_tool_calls_count"]

    def test_perfect_match_non_strict(self) -> None:
        """Test perfect match in non-strict mode."""
        actual = {"tool1": 2, "tool2": 1}
        expected = {"tool1": ("==", 2), "tool2": ("==", 1)}
        score, justification = tool_calls_count_score(actual, expected, strict=False)

        assert score == 1.0
        assert "tool1" in justification["explained_tool_calls_count"]
        assert "tool2" in justification["explained_tool_calls_count"]
        assert "Score: 1.0" in justification["explained_tool_calls_count"]["tool1"]
        assert "Score: 1.0" in justification["explained_tool_calls_count"]["tool2"]

    def test_partial_match_non_strict(self) -> None:
        """Test partial match in non-strict mode."""
        actual = {"tool1": 2, "tool2": 0}
        expected = {"tool1": ("==", 2), "tool2": ("==", 1)}
        score, justification = tool_calls_count_score(actual, expected, strict=False)

        assert score == 0.5  # 1 out of 2 matches
        assert "Score: 1.0" in justification["explained_tool_calls_count"]["tool1"]
        assert "Score: 0.0" in justification["explained_tool_calls_count"]["tool2"]

    def test_mismatch_strict(self) -> None:
        """Test mismatch in strict mode (early return)."""
        actual = {"tool1": 2, "tool2": 0}
        expected = {"tool1": ("==", 2), "tool2": ("==", 1)}
        score, justification = tool_calls_count_score(actual, expected, strict=True)

        # Should return 0 and only include the failing tool
        assert score == 0.0
        assert len(justification["explained_tool_calls_count"]) == 1
        assert "tool2" in justification["explained_tool_calls_count"]

    def test_comparator_operations(self) -> None:
        """Test different comparator operations."""
        actual = {"tool1": 5}

        # Test greater than
        expected_gt = {"tool1": (">", 3)}
        score, justification = tool_calls_count_score(actual, expected_gt, strict=False)
        assert score == 1.0

        # Test less than or equal
        expected_le = {"tool1": ("<=", 5)}
        score, justification = tool_calls_count_score(actual, expected_le, strict=False)
        assert score == 1.0

        # Test not equal
        expected_ne = {"tool1": ("!=", 3)}
        score, justification = tool_calls_count_score(actual, expected_ne, strict=False)
        assert score == 1.0


class TestToolCallsArgsScore:
    """Test tool_calls_args_score helper function."""

    def test_empty_both_lists(self) -> None:
        """Test when both expected and actual lists are empty."""
        score, justification = tool_calls_args_score([], [], strict=False)

        assert score == 1.0
        assert isinstance(justification, dict)
        assert "explained_tool_calls_args" in justification
        assert isinstance(justification["explained_tool_calls_args"], dict)
        assert "_result" in justification["explained_tool_calls_args"]

    def test_empty_actual_list(self) -> None:
        """Test when actual list is empty but expected is not."""
        expected = [ToolCall(name="tool1", args={"arg": "val"})]
        score, justification = tool_calls_args_score([], expected, strict=False)

        assert score == 0.0
        assert isinstance(justification["explained_tool_calls_args"], dict)
        assert "_result" in justification["explained_tool_calls_args"]

    def test_empty_expected_list(self) -> None:
        """Test when expected list is empty but actual is not."""
        actual = [ToolCall(name="tool1", args={"arg": "val"})]
        score, justification = tool_calls_args_score(actual, [], strict=False)

        assert score == 0.0
        assert isinstance(justification["explained_tool_calls_args"], dict)
        assert "_result" in justification["explained_tool_calls_args"]

    def test_perfect_match_exact_mode(self) -> None:
        """Test perfect match in exact mode (default)."""
        actual = [ToolCall(name="tool1", args={"arg1": "val1", "arg2": "val2"})]
        expected = [ToolCall(name="tool1", args={"arg1": "val1", "arg2": "val2"})]
        score, justification = tool_calls_args_score(
            actual, expected, strict=False, subset=False
        )

        assert score == 1.0
        assert "tool1_0" in justification["explained_tool_calls_args"]
        assert "Score: 1.0" in justification["explained_tool_calls_args"]["tool1_0"]

    def test_perfect_match_subset_mode(self) -> None:
        """Test perfect match in subset mode."""
        actual = [
            ToolCall(
                name="tool1", args={"arg1": "val1", "arg2": "val2", "extra": "val"}
            )
        ]
        expected = [ToolCall(name="tool1", args={"arg1": "val1", "arg2": "val2"})]
        score, justification = tool_calls_args_score(
            actual, expected, strict=False, subset=True
        )

        assert score == 1.0
        assert "Score: 1.0" in justification["explained_tool_calls_args"]["tool1_0"]

    def test_mismatch_exact_mode(self) -> None:
        """Test mismatch in exact mode."""
        actual = [ToolCall(name="tool1", args={"arg1": "val1"})]
        expected = [ToolCall(name="tool1", args={"arg1": "val1", "arg2": "val2"})]
        score, justification = tool_calls_args_score(
            actual, expected, strict=False, subset=False
        )

        assert score == 0.0
        assert "Score: 0.0" in justification["explained_tool_calls_args"]["tool1_0"]

    def test_multiple_tool_calls(self) -> None:
        """Test with multiple tool calls."""
        actual = [
            ToolCall(name="tool1", args={"arg1": "val1"}),
            ToolCall(name="tool2", args={"arg2": "val2"}),
        ]
        expected = [
            ToolCall(name="tool1", args={"arg1": "val1"}),
            ToolCall(name="tool2", args={"arg2": "val2"}),
        ]
        score, justification = tool_calls_args_score(actual, expected, strict=False)

        assert score == 1.0
        assert len(justification["explained_tool_calls_args"]) == 2
        assert "tool1_0" in justification["explained_tool_calls_args"]
        assert "tool2_0" in justification["explained_tool_calls_args"]

    def test_strict_mode_with_mismatch(self) -> None:
        """Test strict mode with partial matches."""
        actual = [
            ToolCall(name="tool1", args={"arg1": "val1"}),
            ToolCall(name="tool2", args={"arg2": "wrong"}),
        ]
        expected = [
            ToolCall(name="tool1", args={"arg1": "val1"}),
            ToolCall(name="tool2", args={"arg2": "val2"}),
        ]
        score, justification = tool_calls_args_score(actual, expected, strict=True)

        # In strict mode, partial match should still score proportionally unless all match
        assert score == 0.0  # strict mode requires all to match


class TestToolCallsOutputScore:
    """Test tool_calls_output_score helper function."""

    def test_empty_both_lists(self) -> None:
        """Test when both expected and actual lists are empty."""
        score, justification = tool_calls_output_score([], [], strict=False)

        assert score == 1.0
        assert isinstance(justification, dict)
        assert "explained_tool_calls_outputs" in justification
        assert isinstance(justification["explained_tool_calls_outputs"], dict)
        assert "_result" in justification["explained_tool_calls_outputs"]

    def test_empty_actual_list(self) -> None:
        """Test when actual list is empty but expected is not."""
        expected = [ToolOutput(name="tool1", output="output1")]
        score, justification = tool_calls_output_score([], expected, strict=False)

        assert score == 0.0
        assert isinstance(justification["explained_tool_calls_outputs"], dict)
        assert "_result" in justification["explained_tool_calls_outputs"]

    def test_empty_expected_list(self) -> None:
        """Test when expected list is empty but actual is not."""
        actual = [ToolOutput(name="tool1", output="output1")]
        score, justification = tool_calls_output_score(actual, [], strict=False)

        assert score == 0.0
        assert isinstance(justification["explained_tool_calls_outputs"], dict)
        assert "_result" in justification["explained_tool_calls_outputs"]

    def test_perfect_match_non_strict(self) -> None:
        """Test perfect match in non-strict mode."""
        actual = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="output2"),
        ]
        expected = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="output2"),
        ]
        score, justification = tool_calls_output_score(actual, expected, strict=False)

        assert score == 1.0
        # Check that justifications use per-tool indexed keys
        justification_keys = list(justification["explained_tool_calls_outputs"].keys())
        assert "tool1_0" in justification_keys
        assert "tool2_0" in justification_keys

    def test_perfect_match_strict(self) -> None:
        """Test perfect match in strict mode."""
        actual = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="output2"),
        ]
        expected = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="output2"),
        ]
        score, justification = tool_calls_output_score(actual, expected, strict=True)

        assert score == 1.0

    def test_partial_match_non_strict(self) -> None:
        """Test partial match in non-strict mode."""
        actual = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="wrong_output"),
        ]
        expected = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="output2"),
        ]
        score, justification = tool_calls_output_score(actual, expected, strict=False)

        assert score == 0.5  # 1 out of 2 matches
        # Check individual scores in justification
        justification_values = list(
            justification["explained_tool_calls_outputs"].values()
        )
        assert any("Score: 1.0" in val for val in justification_values)
        assert any("Score: 0.0" in val for val in justification_values)

    def test_mismatch_strict_early_return(self) -> None:
        """Test mismatch in strict mode (early return)."""
        actual = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="wrong_output"),
        ]
        expected = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool2", output="output2"),
        ]
        score, justification = tool_calls_output_score(actual, expected, strict=True)

        # Should return 0 immediately on first mismatch
        assert score == 0.0
        # Should only contain the failing tool call in justification
        assert len(justification["explained_tool_calls_outputs"]) == 1

    def test_duplicate_tool_names(self) -> None:
        """Test with duplicate tool names (one-to-one matching)."""
        actual = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool1", output="output2"),
        ]
        expected = [
            ToolOutput(name="tool1", output="output1"),
            ToolOutput(name="tool1", output="output2"),
        ]
        score, justification = tool_calls_output_score(actual, expected, strict=False)

        assert score == 1.0
        # Should have per-tool indexed keys to distinguish duplicate tool names
        justification_keys = list(justification["explained_tool_calls_outputs"].keys())
        assert "tool1_0" in justification_keys
        assert "tool1_1" in justification_keys


class TestExtractionFunctions:
    """Test extraction functions used by evaluators."""

    @pytest.fixture
    def sample_spans(self) -> list[Any]:
        """Create sample ReadableSpan objects for testing."""
        from opentelemetry.sdk.trace import ReadableSpan

        return [
            ReadableSpan(
                name="tool1",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "tool1",
                    "input.value": "{'arg1': 'value1', 'arg2': 42}",
                    "output.value": '{"content": "result1"}',
                },
            ),
            ReadableSpan(
                name="tool2",
                start_time=1,
                end_time=2,
                attributes={
                    "tool.name": "tool2",
                    "input.value": "{'param': 'test'}",
                    "output.value": '{"content": "result2"}',
                },
            ),
            ReadableSpan(
                name="non_tool_span",
                start_time=2,
                end_time=3,
                attributes={
                    "span.type": "other",
                    "some.data": "value",
                },
            ),
            ReadableSpan(
                name="tool3",
                start_time=3,
                end_time=4,
                attributes={
                    "tool.name": "tool3",
                    "input.value": "{}",
                    "output.value": '{"content": ""}',
                },
            ),
        ]

    @pytest.fixture
    def spans_with_json_input(self) -> list[Any]:
        """Create spans with JSON string input values."""
        from opentelemetry.sdk.trace import ReadableSpan

        return [
            ReadableSpan(
                name="json_tool",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "json_tool",
                    "input.value": '{"key": "value", "number": 123}',
                    "output.value": '{"content": "json_result"}',
                },
            ),
        ]

    @pytest.fixture
    def spans_with_dict_input(self) -> list[Any]:
        """Create spans with dict input values."""
        from opentelemetry.sdk.trace import ReadableSpan

        return [
            ReadableSpan(
                name="dict_tool",
                start_time=0,
                end_time=1,
                attributes={  # pyright: ignore[reportArgumentType]
                    "tool.name": "dict_tool",
                    "input.value": {"direct": "dict", "num": 456},  # type: ignore[dict-item]
                    "output.value": {"content": "dict_result"},  # type: ignore[dict-item]
                },
            ),
        ]

    @pytest.fixture
    def spans_with_invalid_input(self) -> list[Any]:
        """Create spans with invalid input values (for testing input parsing)."""
        from opentelemetry.sdk.trace import ReadableSpan

        return [
            ReadableSpan(
                name="invalid_tool",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "invalid_tool",
                    "input.value": "invalid json {",
                    "output.value": '{"content": "invalid_result"}',
                },
            ),
        ]

    def test_extract_tool_calls_names_empty(self) -> None:
        """Test tool call name extraction with empty list."""
        result = extract_tool_calls_names([])
        assert isinstance(result, list)
        assert result == []

    def test_extract_tool_calls_names_with_tools(self, sample_spans: list[Any]) -> None:
        """Test tool call name extraction with actual tool spans."""
        result = extract_tool_calls_names(sample_spans)

        assert isinstance(result, list)
        assert len(result) == 3  # Only spans with tool.name attribute
        assert result == ["tool1", "tool2", "tool3"]

    def test_extract_tool_calls_names_preserves_order(
        self, sample_spans: list[Any]
    ) -> None:
        """Test that tool call name extraction preserves order."""
        # Reverse the spans to test order preservation
        reversed_spans = list(reversed(sample_spans))
        result = extract_tool_calls_names(reversed_spans)

        # Should be in reverse order since we reversed the input
        expected = ["tool3", "tool2", "tool1"]
        assert result == expected

    def test_extract_tool_calls_names_filters_non_tool_spans(
        self, sample_spans: list[Any]
    ) -> None:
        """Test that non-tool spans are filtered out."""
        result = extract_tool_calls_names(sample_spans)

        # Should not include 'non_tool_span' which doesn't have tool.name
        assert "non_tool_span" not in result
        assert len(result) == 3

    def test_extract_tool_calls_empty(self) -> None:
        """Test tool call extraction with empty list."""
        result = extract_tool_calls([])
        assert isinstance(result, list)
        assert result == []

    def test_extract_tool_calls_with_string_input(
        self, sample_spans: list[Any]
    ) -> None:
        """Test tool call extraction with string input values."""
        result = extract_tool_calls(sample_spans)

        assert isinstance(result, list)
        assert len(result) == 3

        # Check first tool call
        tool1 = result[0]
        assert tool1.name == "tool1"
        assert tool1.args == {"arg1": "value1", "arg2": 42}

        # Check second tool call
        tool2 = result[1]
        assert tool2.name == "tool2"
        assert tool2.args == {"param": "test"}

        # Check third tool call (empty args)
        tool3 = result[2]
        assert tool3.name == "tool3"
        assert tool3.args == {}

    def test_extract_tool_calls_with_dict_input(
        self, spans_with_dict_input: list[Any]
    ) -> None:
        """Test tool call extraction with direct dict input values."""
        result = extract_tool_calls(spans_with_dict_input)

        assert len(result) == 1
        tool_call = result[0]
        assert tool_call.name == "dict_tool"
        assert tool_call.args == {"direct": "dict", "num": 456}

    def test_extract_tool_calls_with_invalid_input(
        self, spans_with_invalid_input: list[Any]
    ) -> None:
        """Test tool call extraction with invalid JSON input."""
        result = extract_tool_calls(spans_with_invalid_input)

        assert len(result) == 1
        tool_call = result[0]
        assert tool_call.name == "invalid_tool"
        assert tool_call.args == {}  # Should default to empty dict on parse error

    def test_extract_tool_calls_missing_input_value(self) -> None:
        """Test tool call extraction when input.value is missing."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="missing_input_tool",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "missing_input_tool",
                # No input.value attribute
                "output.value": "result",
            },
        )

        result = extract_tool_calls([span])
        assert len(result) == 1
        assert result[0].name == "missing_input_tool"
        assert result[0].args == {}

    def test_extract_tool_calls_outputs_empty(self) -> None:
        """Test tool call output extraction with empty list."""
        result = extract_tool_calls_outputs([])
        assert isinstance(result, list)
        assert result == []

    def test_extract_tool_calls_outputs_with_tools(
        self, sample_spans: list[Any]
    ) -> None:
        """Test tool call output extraction with actual tool spans."""
        result = extract_tool_calls_outputs(sample_spans)

        assert isinstance(result, list)
        assert len(result) == 3  # Only spans with tool.name attribute

        # Check outputs
        assert result[0].name == "tool1"
        assert result[0].output == "result1"

        assert result[1].name == "tool2"
        assert result[1].output == "result2"

        assert result[2].name == "tool3"
        assert result[2].output == ""

    def test_extract_tool_calls_outputs_missing_output_value(self) -> None:
        """Test tool call output extraction when output.value is missing."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="missing_output_tool",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "missing_output_tool",
                "input.value": "{}",
                # No output.value attribute
            },
        )

        result = extract_tool_calls_outputs([span])
        assert len(result) == 1
        assert result[0].name == "missing_output_tool"
        assert result[0].output == ""  # Should default to empty string

    def test_extract_tool_calls_outputs_preserves_order(
        self, sample_spans: list[Any]
    ) -> None:
        """Test that tool call output extraction preserves order."""
        result = extract_tool_calls_outputs(sample_spans)

        # Should match the order of spans with tool.name
        expected_names = ["tool1", "tool2", "tool3"]
        actual_names = [output.name for output in result]
        assert actual_names == expected_names

    def test_extract_tool_calls_outputs_filters_non_tool_spans(
        self, sample_spans: list[Any]
    ) -> None:
        """Test that non-tool spans are filtered out from outputs."""
        result = extract_tool_calls_outputs(sample_spans)

        # Should not include outputs from spans without tool.name
        output_names = [output.name for output in result]
        assert "non_tool_span" not in output_names
        assert len(result) == 3

    def test_all_extraction_functions_consistent(self, sample_spans: list[Any]) -> None:
        """Test that all extraction functions return consistent results."""
        names = extract_tool_calls_names(sample_spans)
        calls = extract_tool_calls(sample_spans)
        outputs = extract_tool_calls_outputs(sample_spans)

        # All should return the same number of items
        assert len(names) == len(calls) == len(outputs)

        # Names should match across all extractions
        call_names = [call.name for call in calls]
        output_names = [output.name for output in outputs]

        assert names == call_names == output_names

    def test_extract_tool_calls_outputs_with_invalid_json(self) -> None:
        """Test tool call output extraction with invalid JSON in output.value."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="invalid_json_output_tool",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "invalid_json_output_tool",
                "input.value": "{}",
                "output.value": "not valid json {",
            },
        )

        result = extract_tool_calls_outputs([span])
        assert len(result) == 1
        assert result[0].name == "invalid_json_output_tool"
        # Should use the string as-is when JSON parsing fails
        assert result[0].output == "not valid json {"

    def test_extract_tool_calls_outputs_json_without_content(self) -> None:
        """Test tool call output extraction with JSON that has no content field."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="no_content_tool",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "no_content_tool",
                "input.value": "{}",
                "output.value": '{"status": "success", "data": "some data"}',
            },
        )

        result = extract_tool_calls_outputs([span])
        assert len(result) == 1
        assert result[0].name == "no_content_tool"
        # Should default to empty string when content field is missing
        assert result[0].output == ""

    def test_extract_tool_calls_outputs_with_dict_output(self) -> None:
        """Test tool call output extraction when output.value is already a dict."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="dict_output_tool",
            start_time=0,
            end_time=1,
            attributes={  # pyright: ignore[reportArgumentType]
                "tool.name": "dict_output_tool",
                "input.value": "{}",
                "output.value": {"content": "dict output value"},  # type: ignore[dict-item]
            },
        )

        result = extract_tool_calls_outputs([span])
        assert len(result) == 1
        assert result[0].name == "dict_output_tool"
        assert result[0].output == "dict output value"

    def test_extract_tool_calls_outputs_with_dict_without_content(self) -> None:
        """Test tool call output extraction when output.value is a dict without content field."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="dict_no_content_tool",
            start_time=0,
            end_time=1,
            attributes={  # pyright: ignore[reportArgumentType]
                "tool.name": "dict_no_content_tool",
                "input.value": "{}",
                "output.value": {"result": "some result", "status": "ok"},  # type: ignore[dict-item]
            },
        )

        result = extract_tool_calls_outputs([span])
        assert len(result) == 1
        assert result[0].name == "dict_no_content_tool"
        # Should default to empty string when content field is missing from dict
        assert result[0].output == ""

    def test_extract_tool_calls_outputs_with_non_string_non_dict(self) -> None:
        """Test tool call output extraction with non-string, non-dict output.value."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="numeric_output_tool",
            start_time=0,
            end_time=1,
            attributes={  # pyright: ignore[reportArgumentType]
                "tool.name": "numeric_output_tool",
                "input.value": "{}",
                "output.value": 12345,
            },
        )

        result = extract_tool_calls_outputs([span])
        assert len(result) == 1
        assert result[0].name == "numeric_output_tool"
        # Should convert to string for non-string, non-dict types
        assert result[0].output == "12345"

    def test_extract_tool_calls_outputs_with_json_non_dict_value(self) -> None:
        """Test tool call output extraction when JSON parses to non-dict (e.g., array)."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="json_array_tool",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "json_array_tool",
                "input.value": "{}",
                "output.value": '["item1", "item2", "item3"]',
            },
        )

        result = extract_tool_calls_outputs([span])
        assert len(result) == 1
        assert result[0].name == "json_array_tool"
        # Should use the original string when parsed JSON is not a dict
        assert result[0].output == '["item1", "item2", "item3"]'
