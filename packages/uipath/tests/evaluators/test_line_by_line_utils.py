"""Tests for line-by-line evaluation utility functions."""

import pytest

from uipath.eval.evaluators.line_by_line_utils import (
    aggregate_line_scores,
    build_line_by_line_result,
    evaluate_lines,
    split_into_lines,
    wrap_line_in_structure,
)
from uipath.eval.evaluators.output_evaluator import (
    LineByLineEvaluationDetails,
    LineEvaluationDetail,
)
from uipath.eval.models.models import AgentExecution, NumericEvaluationResult


class TestSplitIntoLines:
    """Tests for split_into_lines utility function."""

    def test_split_with_newline_delimiter(self):
        """Test splitting with default newline delimiter."""
        text = "line1\nline2\nline3"
        result = split_into_lines(text, "\n")
        assert result == ["line1", "line2", "line3"]

    def test_split_with_custom_delimiter(self):
        """Test splitting with custom delimiter."""
        text = "line1|line2|line3"
        result = split_into_lines(text, "|")
        assert result == ["line1", "line2", "line3"]

    def test_split_with_comma_delimiter(self):
        """Test splitting with comma delimiter."""
        text = "apple,banana,cherry"
        result = split_into_lines(text, ",")
        assert result == ["apple", "banana", "cherry"]

    def test_split_filters_empty_lines(self):
        """Test that empty lines are filtered out."""
        text = "line1\n\nline2\n  \nline3"
        result = split_into_lines(text, "\n")
        assert result == ["line1", "line2", "line3"]

    def test_split_with_dict_and_target_key(self):
        """Test splitting when text is a dict and target_output_key is provided."""
        text = {"result": "line1\nline2"}
        result = split_into_lines(text, "\n", target_output_key="result")
        assert result == ["line1", "line2"]

    def test_split_with_dict_and_wildcard_target_key(self):
        """Test splitting when target_output_key is wildcard."""
        text = {"result": "line1\nline2"}
        result = split_into_lines(text, "\n", target_output_key="*")
        # Should convert dict to string
        assert len(result) > 0

    def test_split_converts_non_string_to_string(self):
        """Test that non-string values are converted to string."""
        text = 12345
        result = split_into_lines(text, "\n")
        assert result == ["12345"]

    def test_split_with_multichar_delimiter(self):
        """Test splitting with multi-character delimiter."""
        text = "line1::line2::line3"
        result = split_into_lines(text, "::")
        assert result == ["line1", "line2", "line3"]


class TestWrapLineInStructure:
    """Tests for wrap_line_in_structure utility function."""

    def test_wrap_with_wildcard_target_key(self):
        """Test wrapping with wildcard target key returns line directly."""
        line = "test line"
        result = wrap_line_in_structure(line, "*")
        assert result == "test line"

    def test_wrap_with_none_target_key(self):
        """Test wrapping with None target key returns line directly."""
        line = "test line"
        result = wrap_line_in_structure(line, None)
        assert result == "test line"

    def test_wrap_with_specific_target_key(self):
        """Test wrapping with specific target key returns dict."""
        line = "test line"
        result = wrap_line_in_structure(line, "result")
        assert result == {"result": "test line"}

    def test_wrap_with_empty_string_target_key(self):
        """Test wrapping with empty string target key returns line directly."""
        line = "test line"
        result = wrap_line_in_structure(line, "")
        assert result == "test line"


class TestAggregateLineScores:
    """Tests for aggregate_line_scores utility function."""

    def test_aggregate_numeric_scores(self):
        """Test aggregating numeric scores."""
        mock_results = [
            (1, type("Result", (), {"score": 1.0})()),
            (2, type("Result", (), {"score": 0.5})()),
            (3, type("Result", (), {"score": 0.75})()),
        ]
        result = aggregate_line_scores(mock_results)
        assert result == pytest.approx(0.75)  # (1.0 + 0.5 + 0.75) / 3

    def test_aggregate_boolean_scores(self):
        """Test aggregating boolean scores (converted to float)."""
        mock_results = [
            (1, type("Result", (), {"score": True})()),
            (2, type("Result", (), {"score": False})()),
            (3, type("Result", (), {"score": True})()),
        ]
        result = aggregate_line_scores(mock_results)
        assert result == pytest.approx(0.6667, rel=1e-3)  # (1.0 + 0.0 + 1.0) / 3

    def test_aggregate_mixed_scores(self):
        """Test aggregating mixed numeric and boolean scores."""
        mock_results = [
            (1, type("Result", (), {"score": 1.0})()),
            (2, type("Result", (), {"score": False})()),
            (3, type("Result", (), {"score": 0.5})()),
        ]
        result = aggregate_line_scores(mock_results)
        assert result == 0.5  # (1.0 + 0.0 + 0.5) / 3

    def test_aggregate_empty_results(self):
        """Test aggregating empty results returns 0.0."""
        result = aggregate_line_scores([])
        assert result == 0.0

    def test_aggregate_results_without_score_attribute(self):
        """Test aggregating results without score attribute."""
        mock_results = [
            (1, type("Result", (), {})()),
            (2, type("Result", (), {})()),
        ]
        result = aggregate_line_scores(mock_results)
        assert result == 0.0


class TestEvaluateLines:
    """Tests for evaluate_lines utility function."""

    @pytest.mark.asyncio
    async def test_evaluate_lines_all_match(self):
        """Test evaluating lines when all lines match."""
        actual_lines = ["line1", "line2", "line3"]
        expected_lines = ["line1", "line2", "line3"]

        agent_execution = AgentExecution(
            agent_input={"test": "input"},
            agent_output="line1\nline2\nline3",
            agent_trace=[],
        )

        async def mock_evaluate(execution, criteria):
            return NumericEvaluationResult(score=1.0, details="match")

        def mock_create_criteria(expected_line):
            return {"expected": expected_line}

        line_details, line_results = await evaluate_lines(
            actual_lines=actual_lines,
            expected_lines=expected_lines,
            target_output_key="*",
            agent_execution=agent_execution,
            evaluate_fn=mock_evaluate,
            create_line_criteria_fn=mock_create_criteria,
        )

        assert len(line_details) == 3
        assert len(line_results) == 3
        assert all(isinstance(detail, LineEvaluationDetail) for detail in line_details)
        assert all(detail.score == 1.0 for detail in line_details)

    @pytest.mark.asyncio
    async def test_evaluate_lines_unequal_counts(self):
        """Test evaluating lines when line counts don't match."""
        actual_lines = ["line1", "line2"]
        expected_lines = ["line1", "line2", "line3", "line4"]

        agent_execution = AgentExecution(
            agent_input={"test": "input"},
            agent_output="line1\nline2",
            agent_trace=[],
        )

        async def mock_evaluate(execution, criteria):
            return NumericEvaluationResult(score=1.0, details="match")

        def mock_create_criteria(expected_line):
            return {"expected": expected_line}

        line_details, line_results = await evaluate_lines(
            actual_lines=actual_lines,
            expected_lines=expected_lines,
            target_output_key="*",
            agent_execution=agent_execution,
            evaluate_fn=mock_evaluate,
            create_line_criteria_fn=mock_create_criteria,
        )

        # Should evaluate max(len(actual), len(expected)) = 4 lines
        assert len(line_details) == 4
        assert len(line_results) == 4

        # First 2 lines have content
        assert line_details[0].actual == "line1"
        assert line_details[1].actual == "line2"

        # Last 2 lines are empty for actual
        assert line_details[2].actual == ""
        assert line_details[3].actual == ""

        # All expected lines should be present
        assert line_details[2].expected == "line3"
        assert line_details[3].expected == "line4"

    @pytest.mark.asyncio
    async def test_evaluate_lines_with_target_output_key(self):
        """Test evaluating lines with specific target_output_key."""
        actual_lines = ["line1", "line2"]
        expected_lines = ["line1", "line2"]

        agent_execution = AgentExecution(
            agent_input={"test": "input"},
            agent_output={"result": "line1\nline2"},
            agent_trace=[],
        )

        async def mock_evaluate(execution, criteria):
            # Verify the execution has the wrapped structure
            assert "result" in execution.agent_output
            return NumericEvaluationResult(score=1.0, details="match")

        def mock_create_criteria(expected_line):
            return {"expected": expected_line}

        line_details, line_results = await evaluate_lines(
            actual_lines=actual_lines,
            expected_lines=expected_lines,
            target_output_key="result",
            agent_execution=agent_execution,
            evaluate_fn=mock_evaluate,
            create_line_criteria_fn=mock_create_criteria,
        )

        assert len(line_details) == 2
        assert len(line_results) == 2


class TestBuildLineByLineResult:
    """Tests for build_line_by_line_result utility function."""

    def test_build_result_with_all_matches(self):
        """Test building result when all lines match."""
        line_details = [
            LineEvaluationDetail(
                line_number=1, actual="line1", expected="line1", score=1.0
            ),
            LineEvaluationDetail(
                line_number=2, actual="line2", expected="line2", score=1.0
            ),
        ]

        line_results = [
            (1, NumericEvaluationResult(score=1.0, details="match")),
            (2, NumericEvaluationResult(score=1.0, details="match")),
        ]

        actual_lines = ["line1", "line2"]
        expected_lines = ["line1", "line2"]

        result = build_line_by_line_result(
            line_details=line_details,
            line_results=line_results,
            actual_lines=actual_lines,
            expected_lines=expected_lines,
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        assert hasattr(result, "_line_by_line_results")
        assert isinstance(result.details, LineByLineEvaluationDetails)
        assert result.details.total_lines_actual == 2
        assert result.details.total_lines_expected == 2

    def test_build_result_with_partial_matches(self):
        """Test building result with partial matches."""
        line_details = [
            LineEvaluationDetail(
                line_number=1, actual="line1", expected="line1", score=1.0
            ),
            LineEvaluationDetail(
                line_number=2, actual="wrong", expected="line2", score=0.0
            ),
            LineEvaluationDetail(
                line_number=3, actual="line3", expected="line3", score=1.0
            ),
        ]

        line_results = [
            (1, NumericEvaluationResult(score=1.0, details="match")),
            (2, NumericEvaluationResult(score=0.0, details="no match")),
            (3, NumericEvaluationResult(score=1.0, details="match")),
        ]

        actual_lines = ["line1", "wrong", "line3"]
        expected_lines = ["line1", "line2", "line3"]

        result = build_line_by_line_result(
            line_details=line_details,
            line_results=line_results,
            actual_lines=actual_lines,
            expected_lines=expected_lines,
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == pytest.approx(0.6667, rel=1e-3)  # 2/3

    def test_build_result_with_unequal_line_counts(self):
        """Test building result when actual and expected have different line counts."""
        line_details = [
            LineEvaluationDetail(
                line_number=1, actual="line1", expected="line1", score=1.0
            ),
            LineEvaluationDetail(line_number=2, actual="", expected="line2", score=0.0),
        ]

        line_results = [
            (1, NumericEvaluationResult(score=1.0, details="match")),
            (2, NumericEvaluationResult(score=0.0, details="no match")),
        ]

        actual_lines = ["line1"]
        expected_lines = ["line1", "line2"]

        result = build_line_by_line_result(
            line_details=line_details,
            line_results=line_results,
            actual_lines=actual_lines,
            expected_lines=expected_lines,
        )

        assert isinstance(result, NumericEvaluationResult)
        assert isinstance(result.details, LineByLineEvaluationDetails)
        assert result.details.total_lines_actual == 1
        assert result.details.total_lines_expected == 2
        assert result.score == 0.5  # 1/2
