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
        assert "actual" in justification
        assert "expected" in justification
        assert "lcs" in justification
        assert justification["lcs"] == []

    def test_empty_actual_list(self) -> None:
        """Test when actual list is empty but expected is not."""
        score, justification = tool_calls_order_score([], ["tool1"], strict=False)

        assert score == 0.0
        assert isinstance(justification, dict)
        assert justification["actual"] == str([])
        assert justification["expected"] == str(["tool1"])
        assert justification["lcs"] == []

    def test_empty_expected_list(self) -> None:
        """Test when expected list is empty but actual is not."""
        score, justification = tool_calls_order_score(["tool1"], [], strict=False)

        assert score == 0.0
        assert isinstance(justification, dict)
        assert justification["actual"] == str(["tool1"])
        assert justification["expected"] == str([])
        assert justification["lcs"] == []

    def test_perfect_match_non_strict(self) -> None:
        """Test perfect match in non-strict mode."""
        actual = ["tool1", "tool2", "tool3"]
        expected = ["tool1", "tool2", "tool3"]
        score, justification = tool_calls_order_score(actual, expected, strict=False)

        assert score == 1.0
        assert justification["lcs"] == expected
        assert justification["actual"] == str(actual)
        assert justification["expected"] == str(expected)

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

    def test_extractors_skip_synthesized_tool_spans(self) -> None:
        """Spans tagged with tool.synthesized=True (BPMN container spans
        synthesized for trajectory rendering) must be filtered from all three
        per-call extractors so they don't pollute tool-call evaluator actuals.
        """
        from opentelemetry.sdk.trace import ReadableSpan

        synth_process = ReadableSpan(
            name="Instance: abc",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "FlowExecution",
                "tool.synthesized": True,
                "input.value": '{"instanceId": "abc"}',
                "output.value": "Status: Completed",
            },
        )
        synth_element = ReadableSpan(
            name="Autonomous Agent",
            start_time=2,
            end_time=3,
            attributes={
                "tool.name": "ServiceTask: Autonomous Agent",
                "tool.synthesized": True,
                "input.value": "{}",
                "output.value": "Status: Completed",
            },
        )
        real_tool = ReadableSpan(
            name="Tool call - web_search",
            start_time=4,
            end_time=5,
            attributes={
                "tool.name": "web_search",
                "input.value": '{"query": "x"}',
                "output.value": '{"content": "ok"}',
            },
        )

        spans = [synth_process, synth_element, real_tool]

        assert extract_tool_calls_names(spans) == ["web_search"]
        calls = extract_tool_calls(spans)
        assert [c.name for c in calls] == ["web_search"]
        outputs = extract_tool_calls_outputs(spans)
        assert [o.name for o in outputs] == ["web_search"]

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


class TestIdAwareExtraction:
    """Verify tool.id propagation through the three extractors, plus the
    include_args=False optimization and the JSON-first parse fallback.
    """

    def test_extractors_read_tool_id_when_present(self) -> None:
        """When a span carries `tool.id`, it must surface on ToolCall/ToolOutput.id."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="Tool call - Web_Search",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "Web_Search",
                "tool.id": "7abae702-f898-4cc9-95f1-c365b9a857f9",
                "input.value": "{}",
                "output.value": '{"content": "ok"}',
            },
        )
        calls = extract_tool_calls([span])
        outputs = extract_tool_calls_outputs([span])
        assert calls[0].id == "7abae702-f898-4cc9-95f1-c365b9a857f9"
        assert calls[0].name == "Web_Search"
        assert outputs[0].id == "7abae702-f898-4cc9-95f1-c365b9a857f9"
        assert outputs[0].name == "Web_Search"

    def test_extractors_preserve_falsy_but_present_tool_id(self) -> None:
        """tool.id of 0 or empty string is unusual but legal — must not be silently dropped.

        Original code used `if tool_id` which would treat 0 / '' as missing.
        Fix uses `is not None`.
        """
        from opentelemetry.sdk.trace import ReadableSpan

        for falsy_id in (0, "", False):
            span = ReadableSpan(
                name="t",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "f",
                    "tool.id": falsy_id,
                    "input.value": "{}",
                    "output.value": '{"content": "ok"}',
                },
            )
            calls = extract_tool_calls([span])
            outputs = extract_tool_calls_outputs([span])
            assert calls[0].id == str(falsy_id), f"falsy id {falsy_id!r} was dropped"
            assert outputs[0].id == str(falsy_id), f"falsy id {falsy_id!r} was dropped"

    def test_extract_tool_calls_parses_json_literals(self) -> None:
        """input.value with JSON `true`/`false`/`null` should parse cleanly.

        `ast.literal_eval` doesn't recognise those tokens (Python uses
        True/False/None); the extractor now tries `json.loads` first and only
        falls back to `ast.literal_eval` on JSON parse failure.
        """
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="t",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "t",
                "input.value": '{"a": true, "b": false, "c": null}',
            },
        )
        calls = extract_tool_calls([span])
        assert calls[0].args == {"a": True, "b": False, "c": None}

    def test_extract_tool_calls_falls_back_to_python_literal(self) -> None:
        """Single-quoted Python dict repr (the historical input shape) still parses."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="t",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "t",
                "input.value": "{'a': 1, 'b': 'two'}",  # JSON-invalid, Python-valid
            },
        )
        calls = extract_tool_calls([span])
        assert calls[0].args == {"a": 1, "b": "two"}

    def test_extract_tool_calls_non_dict_parsed_result_yields_empty_args(self) -> None:
        """If input.value parses to a non-dict (e.g. a bare string), args→{}.

        Avoids pydantic validation failures from feeding a non-dict into
        ToolCall(args=...).
        """
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="t",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "t",
                "input.value": '"hello"',  # JSON-valid string, not a dict
            },
        )
        calls = extract_tool_calls([span])
        assert calls[0].args == {}

    def test_extract_tool_calls_include_args_false_skips_parse(self) -> None:
        """With include_args=False, broken input.value is not parsed and doesn't raise.

        Used by count / order evaluators that don't need args.
        """
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="t",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "t",
                "tool.id": "abc",
                "input.value": "this is not valid python or json{{{",
            },
        )
        calls = extract_tool_calls([span], include_args=False)
        assert len(calls) == 1
        assert calls[0].name == "t"
        assert calls[0].id == "abc"
        assert calls[0].args == {}  # short-circuited, not parsed

    def test_extractors_default_id_to_none_when_absent(self) -> None:
        """Spans without `tool.id` produce ToolCall/ToolOutput with id=None (back-compat)."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = ReadableSpan(
            name="Tool call - legacy",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "legacy_tool",
                "input.value": "{}",
                "output.value": '{"content": "ok"}',
            },
        )
        calls = extract_tool_calls([span])
        outputs = extract_tool_calls_outputs([span])
        assert calls[0].id is None
        assert outputs[0].id is None


class TestIdAwareMatching:
    """Verify id-aware matching across all four tool-call scoring functions.

    For each function: an Expected criterion authored against the tool's id
    matches the actual call when the actual carries the same id, even if the
    `name` differs (the common case after a tool rename or the
    'Web Search' → 'Web_Search' display-vs-runtime divergence).
    """

    def test_args_score_matches_by_id_when_names_differ(self) -> None:
        """Expected keyed by id matches actual with same id but different name."""
        from uipath.eval._helpers.evaluators_helpers import tool_calls_args_score

        actual = [ToolCall(name="Web_Search", id="uuid-1", args={"q": "x"})]
        expected = [ToolCall(name="Web Search", id="uuid-1", args={"q": "x"})]
        score, _ = tool_calls_args_score(actual, expected)
        assert score == 1.0

    def test_args_score_falls_back_to_name_when_id_missing(self) -> None:
        """Legacy eval-set without id still matches by name (back-compat)."""
        from uipath.eval._helpers.evaluators_helpers import tool_calls_args_score

        actual = [ToolCall(name="Web_Search", id="uuid-1", args={"q": "x"})]
        expected = [ToolCall(name="Web_Search", args={"q": "x"})]
        score, _ = tool_calls_args_score(actual, expected)
        assert score == 1.0

    def test_args_score_no_match_when_ids_differ(self) -> None:
        """Different ids → no match even with same name."""
        from uipath.eval._helpers.evaluators_helpers import tool_calls_args_score

        actual = [ToolCall(name="Web_Search", id="uuid-A", args={"q": "x"})]
        expected = [ToolCall(name="Web_Search", id="uuid-B", args={"q": "x"})]
        score, _ = tool_calls_args_score(actual, expected)
        assert score == 0.0

    def test_output_score_matches_by_id(self) -> None:
        from uipath.eval._helpers.evaluators_helpers import tool_calls_output_score

        actual = [ToolOutput(name="Web_Search", id="uuid-1", output="ok")]
        expected = [ToolOutput(name="Web Search", id="uuid-1", output="ok")]
        score, _ = tool_calls_output_score(actual, expected)
        assert score == 1.0

    def test_count_by_name_and_id_helper(self) -> None:
        """Each call contributes one unit to its name AND to its id key."""
        from uipath.eval._helpers.evaluators_helpers import (
            count_tool_calls_by_name_and_id,
        )

        calls = [
            ToolCall(name="Web_Search", id="uuid-1", args={}),
            ToolCall(name="Web_Search", id="uuid-1", args={}),
            ToolCall(name="get_temp", args={}),  # no id
        ]
        counts = count_tool_calls_by_name_and_id(calls)
        assert counts["Web_Search"] == 2
        assert counts["uuid-1"] == 2  # same calls retrievable by id
        assert counts["get_temp"] == 1

    def test_order_score_with_ids_matches_id_keyed_expected(self) -> None:
        """LCS treats expected key as match if it equals actual.id OR actual.name."""
        from uipath.eval._helpers.evaluators_helpers import (
            tool_calls_order_score_with_ids,
        )

        actual = [
            ToolCall(name="Web_Search", id="uuid-1", args={}),
            ToolCall(name="Web_Search", id="uuid-1", args={}),
        ]
        # Expected authored by id
        score, _ = tool_calls_order_score_with_ids(actual, ["uuid-1", "uuid-1"])
        assert score == 1.0
        # Expected authored by name (legacy)
        score, _ = tool_calls_order_score_with_ids(actual, ["Web_Search", "Web_Search"])
        assert score == 1.0
        # Mixed: works either way
        score, _ = tool_calls_order_score_with_ids(actual, ["uuid-1", "Web_Search"])
        assert score == 1.0

    def test_order_score_with_ids_back_compat_when_id_absent(self) -> None:
        """When actual has no ids (legacy traces), comparison is name-only."""
        from uipath.eval._helpers.evaluators_helpers import (
            tool_calls_order_score_with_ids,
        )

        actual = [
            ToolCall(name="get_temp", args={}),
            ToolCall(name="get_humidity", args={}),
        ]
        score, _ = tool_calls_order_score_with_ids(actual, ["get_temp", "get_humidity"])
        assert score == 1.0


class TestSanitizedNameMatch:
    """Sanitised-name fallback in ``_match_key`` and ``_calls_match``.

    The display name the editor persists (``"Web Search"``) must match the
    sanitised name the LangChain runtime emits as ``tool.name``
    (``"Web_Search"``). Both sides are normalised through the same regex.
    """

    def _reference_sanitize(self, name: str) -> str:
        """Pinned copy of ``uipath_langchain.agent.tools.utils.sanitize_tool_name``.

        Kept here intentionally rather than imported live — ``uipath_langchain``
        is not a dep of ``uipath`` (wrong direction). If the LangChain
        sanitiser changes upstream, this copy must be updated together with
        ``_normalize_tool_name`` in ``evaluators_helpers``.
        """
        import re

        trim_whitespaces = "_".join(name.split())
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", trim_whitespaces)
        return sanitized[:64]

    @pytest.mark.parametrize(
        "raw",
        [
            "Web Search",
            "Google Sheets / Read",
            "Add Numbers",
            "tool with spaces and (parens)",
            "snake_case_tool",
            "kebab-case-tool",
            "alreadySanitised",
            "  multiple   whitespace  ",
            "very-long-name-" + "x" * 100,
            "",
        ],
    )
    def test_normalize_matches_langchain_reference(self, raw: str) -> None:
        from uipath.eval._helpers.evaluators_helpers import _normalize_tool_name

        assert _normalize_tool_name(raw) == self._reference_sanitize(raw)

    def test_normalize_handles_none(self) -> None:
        from uipath.eval._helpers.evaluators_helpers import _normalize_tool_name

        assert _normalize_tool_name(None) == ""

    def test_match_key_display_name_vs_sanitised_actual(self) -> None:
        """Editor saved ``"Web Search"``; runtime emitted ``"Web_Search"``."""
        from uipath.eval._helpers.evaluators_helpers import _match_key

        assert _match_key("Web_Search", None, "Web Search") is True

    def test_match_key_id_still_wins_when_present(self) -> None:
        from uipath.eval._helpers.evaluators_helpers import _match_key

        assert _match_key("Web_Search", "uuid-1", "uuid-1") is True
        assert _match_key("Web_Search", "uuid-1", "Web Search") is True

    def test_match_key_mismatch_after_sanitising(self) -> None:
        from uipath.eval._helpers.evaluators_helpers import _match_key

        assert _match_key("Web_Search", None, "Image_Search") is False

    def test_calls_match_display_vs_sanitised(self) -> None:
        from uipath.eval._helpers.evaluators_helpers import _calls_match

        actual = ToolCall(name="Web_Search", args={})
        expected = ToolCall(name="Web Search", args={})
        assert _calls_match(actual, expected) is True

    def test_calls_match_id_equality_unchanged(self) -> None:
        from uipath.eval._helpers.evaluators_helpers import _calls_match

        actual = ToolCall(name="Web_Search", id="uuid-1", args={})
        expected = ToolCall(name="totally different", id="uuid-1", args={})
        assert _calls_match(actual, expected) is True

    def test_calls_match_output_display_vs_sanitised(self) -> None:
        from uipath.eval._helpers.evaluators_helpers import _calls_match

        actual = ToolOutput(name="Web_Search", output="x")
        expected = ToolOutput(name="Web Search", output="x")
        assert _calls_match(actual, expected) is True

    def test_count_score_display_name_matches_sanitised_actual(self) -> None:
        """Count scorer must close the same display-vs-sanitised gap.

        ``tool_calls_count_score`` does raw dict lookup, not ``_match_key``,
        so it needs its own sanitisation fallback. Without it, an editor
        criterion keyed by ``"Web Search"`` misses the actual counts keyed by
        ``"Web_Search"`` and scores 0.
        """
        actual = {"Web_Search": 2}
        expected = {"Web Search": ("==", 2)}
        score, _ = tool_calls_count_score(actual, expected)
        assert score == 1.0

    def test_count_score_id_keyed_expected_still_wins(self) -> None:
        """When the editor saves an id-keyed criterion, raw lookup hits first."""
        actual = {"Web_Search": 1, "uuid-web-1": 1}
        expected = {"uuid-web-1": (">=", 1)}
        score, _ = tool_calls_count_score(actual, expected)
        assert score == 1.0

    def test_count_score_strict_mode_passes_on_display_name(self) -> None:
        actual = {"Web_Search": 1}
        expected = {"Web Search": ("==", 1)}
        score, _ = tool_calls_count_score(actual, expected, strict=True)
        assert score == 1.0

    def test_count_score_strict_mode_fails_on_count_mismatch(self) -> None:
        """Sanitisation closes name gap but a wrong count still fails strict."""
        actual = {"Web_Search": 1}
        expected = {"Web Search": ("==", 3)}
        score, _ = tool_calls_count_score(actual, expected, strict=True)
        assert score == 0.0
