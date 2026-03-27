"""Tests for LegacyCSVExactMatchEvaluator.

Tests CSV column exact matching functionality including:
- Single and multiple column comparisons
- Case-insensitive column names
- Various CSV formats
- Job attachment support
- Line-by-line evaluation
"""

from typing import Any
from unittest.mock import patch

import pytest

from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.evaluators.legacy_csv_exact_match_evaluator import (
    LegacyCSVExactMatchEvaluator,
)
from uipath.eval.evaluators.output_evaluator import LineByLineEvaluationDetails
from uipath.eval.models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


def _make_base_params(target_sub_output_key: str = "Name") -> dict[str, Any]:
    """Create base parameters for CSV evaluator."""
    return {
        "id": "csv_exact_match",
        "category": LegacyEvaluatorCategory.Deterministic,
        "type": LegacyEvaluatorType.CSVColumnExactMatch,
        "name": "CSVExactMatch",
        "description": "Evaluates exact match of CSV columns",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "targetSubOutputKey": target_sub_output_key,
    }


@pytest.fixture
def evaluator_single_column():
    """Fixture to create evaluator with single column."""
    with patch("uipath.platform.UiPath"):
        return LegacyCSVExactMatchEvaluator(
            **_make_base_params(target_sub_output_key="Name")
        )


@pytest.fixture
def evaluator_multiple_columns():
    """Fixture to create evaluator with multiple columns."""
    with patch("uipath.platform.UiPath"):
        return LegacyCSVExactMatchEvaluator(
            **_make_base_params(target_sub_output_key="Name,Age")
        )


class TestLegacyCSVExactMatchEvaluator:
    """Test suite for LegacyCSVExactMatchEvaluator."""

    @pytest.mark.asyncio
    async def test_single_column_match(self, evaluator_single_column) -> None:
        """Test exact match with single column."""
        csv_content = "Name,Age,City\nJohn,25,Paris"
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator_single_column.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_multiple_columns_match(self, evaluator_multiple_columns) -> None:
        """Test exact match with multiple columns."""
        csv_content = "Name,Age,City\nJohn,25,Paris"
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator_multiple_columns.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_column_value_differs(self, evaluator_single_column) -> None:
        """Test when column values differ."""
        actual_csv = "Name,Age,City\nJohn,25,Paris"
        expected_csv = "Name,Age,City\nJane,25,Paris"  # Different name

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=actual_csv,
        )

        result = await evaluator_single_column.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": expected_csv},
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_case_insensitive_column_names(self) -> None:
        """Test case-insensitive column name matching."""
        with patch("uipath.platform.UiPath"):
            evaluator = LegacyCSVExactMatchEvaluator(
                **_make_base_params(target_sub_output_key="NAME,age")
            )

        csv_content = "name,AGE,CiTy\nJohn,25,Paris"
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_json_element_with_content_property(
        self, evaluator_single_column
    ) -> None:
        """Test handling dict with 'content' property."""
        csv_content = "Name,Age\nJohn,25"
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"content": csv_content},
        )

        result = await evaluator_single_column.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_empty_target_sub_output_key_raises_error(self) -> None:
        """Test that empty targetSubOutputKey raises ValueError."""
        with patch("uipath.platform.UiPath"):
            with pytest.raises(
                ValueError, match="target_sub_output_key must not be empty"
            ):
                LegacyCSVExactMatchEvaluator(
                    **_make_base_params(target_sub_output_key="")
                )

    @pytest.mark.asyncio
    async def test_column_not_found_returns_error(
        self, evaluator_single_column
    ) -> None:
        """Test that missing column returns error result."""
        csv_content = "Name,Age\nJohn,25"

        # Create evaluator with non-existent column
        with patch("uipath.platform.UiPath"):
            evaluator = LegacyCSVExactMatchEvaluator(
                **_make_base_params(target_sub_output_key="NonExistentColumn")
            )

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        # Should return error result
        assert isinstance(result.details, str)
        assert "Missing columns: NonExistentColumn" in result.details

    @pytest.mark.asyncio
    async def test_empty_csv_returns_error(self, evaluator_single_column) -> None:
        """Test that empty CSV returns error result."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="",
        )

        result = await evaluator_single_column.validate_and_evaluate_criteria(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": "Name,Age\nJohn,25"},
                expected_agent_behavior="",
            ),
        )

        # Should return error result
        assert "CSV output is null or empty" in result.details

    @pytest.mark.asyncio
    async def test_complex_csv_with_quotes_and_commas(
        self, evaluator_multiple_columns
    ) -> None:
        """Test handling CSV with quotes and commas in values."""
        with patch("uipath.platform.UiPath"):
            evaluator = LegacyCSVExactMatchEvaluator(
                **_make_base_params(target_sub_output_key="Name,Description")
            )

        csv_content = (
            'Name,Description,Status\n"John, Jr.","Software Engineer, Senior","Active"'
        )
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_empty_values(self) -> None:
        """Test handling empty column values."""
        with patch("uipath.platform.UiPath"):
            evaluator = LegacyCSVExactMatchEvaluator(
                **_make_base_params(target_sub_output_key="Age")
            )

        csv_content = "Name,Age,City\nJohn,,Paris"
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_no_data_rows_returns_error(self, evaluator_single_column) -> None:
        """Test that CSV with headers but no data rows returns error result."""
        csv_content = "Name,Age"  # Headers only, no data
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator_single_column.validate_and_evaluate_criteria(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        # Should return error result
        assert "CSV must contain one data row" in result.details

    @pytest.mark.asyncio
    async def test_whitespace_only_target_columns_returns_error(self) -> None:
        """Test that whitespace-only targetSubOutputKey returns error result."""
        with patch("uipath.platform.UiPath"):
            evaluator = LegacyCSVExactMatchEvaluator(
                **_make_base_params(target_sub_output_key=" , , ")
            )

        csv_content = "Name,Age\nJohn,25"
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        # Should return error result
        assert isinstance(result.details, str)
        assert "At least one target column must be specified" in result.details

    @pytest.mark.asyncio
    async def test_expected_output_without_content_property_returns_error(
        self, evaluator_single_column
    ) -> None:
        """Test that expected output without 'content' property returns error result."""
        csv_content = "Name,Age\nJohn,25"
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=csv_content,
        )

        # Expected output as empty string
        result = await evaluator_single_column.validate_and_evaluate_criteria(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output="",
                expected_agent_behavior="",
            ),
        )

        # Should return error result
        assert "CSV output is null or empty" in result.details

    # Note: Python's csv module is more lenient than C# CsvHelper and handles most
    # malformed CSVs gracefully. Invalid CSV errors are rare in practice.

    @pytest.mark.asyncio
    async def test_actual_missing_column_in_comparison(self) -> None:
        """Test when actual CSV is missing a column that's in expected."""
        with patch("uipath.platform.UiPath"):
            evaluator = LegacyCSVExactMatchEvaluator(
                **_make_base_params(target_sub_output_key="Name,Age")
            )

        actual_csv = "Name\nJohn"  # Missing Age column
        expected_csv = "Name,Age\nJohn,25"

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=actual_csv,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": expected_csv},
                expected_agent_behavior="",
            ),
        )

        # Should return error result
        assert isinstance(result.details, str)
        assert "Missing columns: Age" in result.details

    @pytest.mark.asyncio
    async def test_whitespace_trimming_in_values(self, evaluator_single_column) -> None:
        """Test that whitespace is trimmed from column values."""
        actual_csv = "Name,Age\n  John  ,25"
        expected_csv = "Name,Age\nJohn,25"

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=actual_csv,
        )

        result = await evaluator_single_column.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": expected_csv},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_case_sensitive_value_comparison(
        self, evaluator_single_column
    ) -> None:
        """Test that value comparison is case-sensitive."""
        actual_csv = "Name,Age\nJohn,25"
        expected_csv = "Name,Age\njohn,25"  # Different case

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=actual_csv,
        )

        result = await evaluator_single_column.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": expected_csv},
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_extra_columns_are_ignored(self, evaluator_single_column) -> None:
        """Test that extra columns not in targetSubOutputKey are ignored."""
        actual_csv = "Name,Age,City,Country\nJohn,25,Paris,France"
        expected_csv = "Name,Age,City\nJohn,30,London"  # Different Age and City, but we only check Name

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=actual_csv,
        )

        result = await evaluator_single_column.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": expected_csv},
                expected_agent_behavior="",
            ),
        )

        # Should match because we only check the "Name" column
        assert result.score is True


# Line-by-line evaluation tests
# CSV evaluator overrides _evaluate_line_by_line to preserve headers
@pytest.mark.asyncio
async def test_line_by_line_all_match():
    """Test line-by-line evaluation when all CSV data rows match."""
    with patch("uipath.platform.UiPath"):
        evaluator = LegacyCSVExactMatchEvaluator(
            **_make_base_params(target_sub_output_key="Name"),
            lineByLineEvaluation=True,
            lineDelimiter="\n",
        )

    csv_content = "Name,Age\nJohn,25\nJane,30\nBob,35"
    agent_execution = AgentExecution(
        agent_input={"input": "test"},
        agent_output=csv_content,
        agent_trace=[],
    )

    result = await evaluator.validate_and_evaluate_criteria(
        agent_execution=agent_execution,
        evaluation_criteria=LegacyEvaluationCriteria(
            expected_output={"content": csv_content},
            expected_agent_behavior="",
        ),
    )

    # All 3 data rows match, so score should be 1.0
    assert result.score == 1.0
    assert hasattr(result, "details")
    assert isinstance(result.details, LineByLineEvaluationDetails)
    # total_lines counts data rows only (not header)
    assert result.details.total_lines_actual == 3
    assert result.details.total_lines_expected == 3
    assert len(result.details.line_by_line_results) == 3


@pytest.mark.asyncio
async def test_line_by_line_partial_match():
    """Test line-by-line evaluation with partial matches."""
    with patch("uipath.platform.UiPath"):
        evaluator = LegacyCSVExactMatchEvaluator(
            **_make_base_params(target_sub_output_key="Name"),
            lineByLineEvaluation=True,
            lineDelimiter="\n",
        )

    actual_csv = "Name,Age\nJohn,25\nDifferent,30\nBob,35"
    expected_csv = "Name,Age\nJohn,25\nJane,30\nBob,35"

    agent_execution = AgentExecution(
        agent_input={"input": "test"},
        agent_output=actual_csv,
        agent_trace=[],
    )

    result = await evaluator.validate_and_evaluate_criteria(
        agent_execution=agent_execution,
        evaluation_criteria=LegacyEvaluationCriteria(
            expected_output={"content": expected_csv},
            expected_agent_behavior="",
        ),
    )

    # 2 out of 3 data rows match, so score should be ~0.67
    assert 0.6 < result.score < 0.7
    assert hasattr(result, "details")
    assert isinstance(result.details, LineByLineEvaluationDetails)
    assert result.details.total_lines_actual == 3
    assert result.details.total_lines_expected == 3
    assert len(result.details.line_by_line_results) == 3

    # Check individual line scores
    assert result.details.line_by_line_results[0].score == 1.0  # John matches
    assert result.details.line_by_line_results[1].score == 0.0  # Different != Jane
    assert result.details.line_by_line_results[2].score == 1.0  # Bob matches


@pytest.mark.asyncio
async def test_line_by_line_multiple_columns():
    """Test line-by-line evaluation with multiple columns."""
    with patch("uipath.platform.UiPath"):
        evaluator = LegacyCSVExactMatchEvaluator(
            **_make_base_params(target_sub_output_key="Name,Age"),
            lineByLineEvaluation=True,
            lineDelimiter="\n",
        )

    csv_content = "Name,Age,City\nJohn,25,Paris\nJane,30,London"
    agent_execution = AgentExecution(
        agent_input={"input": "test"},
        agent_output=csv_content,
        agent_trace=[],
    )

    result = await evaluator.validate_and_evaluate_criteria(
        agent_execution=agent_execution,
        evaluation_criteria=LegacyEvaluationCriteria(
            expected_output={"content": csv_content},
            expected_agent_behavior="",
        ),
    )

    # All rows match on Name and Age, so score should be 1.0
    assert result.score == 1.0
    assert isinstance(result.details, LineByLineEvaluationDetails)
    assert result.details.total_lines_actual == 2
    assert result.details.total_lines_expected == 2


@pytest.mark.asyncio
async def test_line_by_line_unequal_line_counts():
    """Test line-by-line evaluation with different line counts."""
    with patch("uipath.platform.UiPath"):
        evaluator = LegacyCSVExactMatchEvaluator(
            **_make_base_params(target_sub_output_key="Name"),
            lineByLineEvaluation=True,
            lineDelimiter="\n",
        )

    actual_csv = "Name,Age\nJohn,25\nJane,30"  # 2 data rows
    expected_csv = "Name,Age\nJohn,25\nJane,30\nBob,35"  # 3 data rows

    agent_execution = AgentExecution(
        agent_input={"input": "test"},
        agent_output=actual_csv,
        agent_trace=[],
    )

    result = await evaluator.validate_and_evaluate_criteria(
        agent_execution=agent_execution,
        evaluation_criteria=LegacyEvaluationCriteria(
            expected_output={"content": expected_csv},
            expected_agent_behavior="",
        ),
    )

    # 2 out of 3 lines match (third line is missing), so score should be ~0.67
    assert 0.6 < result.score < 0.7
    assert isinstance(result.details, LineByLineEvaluationDetails)
    assert result.details.total_lines_actual == 2
    assert result.details.total_lines_expected == 3
    assert len(result.details.line_by_line_results) == 3  # Evaluates max(2, 3) lines


@pytest.mark.asyncio
async def test_line_by_line_with_job_attachment():
    """Test line-by-line evaluation with job attachment (mocked)."""
    with patch("uipath.platform.UiPath"):
        evaluator = LegacyCSVExactMatchEvaluator(
            **_make_base_params(target_sub_output_key="Name"),
            lineByLineEvaluation=True,
            lineDelimiter="\n",
        )

    # Mock job attachment download
    csv_content = "Name,Age\nJohn,25\nJane,30"

    with patch(
        "uipath.eval.evaluators.base_legacy_evaluator.download_attachment_as_string",
        return_value=csv_content,
    ):
        agent_execution = AgentExecution(
            agent_input={"input": "test"},
            # Simulate job attachment URI
            agent_output="urn:uipath:cas:file:orchestrator:12345678-1234-1234-1234-123456789abc",
            agent_trace=[],
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"content": csv_content},
                expected_agent_behavior="",
            ),
        )

        # All lines match, so score should be 1.0
        assert result.score == 1.0
        assert isinstance(result.details, LineByLineEvaluationDetails)
        assert result.details.total_lines_actual == 2
        assert result.details.total_lines_expected == 2


# Note: Custom delimiters work but CSV must still use commas for column separation
# Line-by-line evaluation with custom delimiter would split "Name,Age|John,25|Jane,30"
# into ["Name,Age", "John,25", "Jane,30"] which creates valid CSV rows.
