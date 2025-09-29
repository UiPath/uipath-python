"""Test module for evaluation result aggregation logic.

This module tests the deduplication and aggregation functionality
that mirrors the original _calculate_test_results_core logic.
"""

import pytest

from src.uipath.eval._helpers.coded_evaluators_helpers import (
    calculate_final_score,
    generate_datapoint_id,
)
from src.uipath.eval.models import (
    AgentExecution,
    EvaluationResult,
    NumericEvaluationResult,
)


class TestDatapointIdGeneration:
    """Test datapoint ID generation from agent inputs."""

    def test_generate_datapoint_id_with_arbitrary_field(self) -> None:
        """Test datapoint ID generation with arbitrary field name."""
        agent_execution = AgentExecution(
            agent_input={"some_random_field": "What is the weather like today?"},
            agent_output={},
            agent_trace=[],
        )
        datapoint_id = generate_datapoint_id(agent_execution)

        assert datapoint_id.startswith("what_is_the_weather_like_today")
        assert len(datapoint_id.split("_")[-1]) == 8  # Hash part should be 8 chars
        assert "_" in datapoint_id

    def test_generate_datapoint_id_with_long_text(self) -> None:
        """Test datapoint ID generation with long text (should truncate)."""
        agent_execution = AgentExecution(
            agent_input={
                "user_message": "This is a very long question that should be truncated to fit within the 30 character limit for readability"
            },
            agent_output={},
            agent_trace=[],
        )
        datapoint_id = generate_datapoint_id(agent_execution)

        readable_part = datapoint_id.split("_")[:-1]  # All parts except hash
        readable_text = "_".join(readable_part)
        assert len(readable_text) <= 30
        assert datapoint_id.startswith("this_is_a_very_long_question_t")

    def test_generate_datapoint_id_with_special_chars(self) -> None:
        """Test datapoint ID generation removes special characters."""
        agent_execution = AgentExecution(
            agent_input={"content": "Hello, world! How are you? @#$%"},
            agent_output={},
            agent_trace=[],
        )
        datapoint_id = generate_datapoint_id(agent_execution)

        # Should only contain alphanumeric, underscore, and hash
        import re

        assert re.match(r"^[a-z0-9_]+$", datapoint_id)
        assert "hello_world_how_are_you" in datapoint_id

    def test_generate_datapoint_id_empty_input(self) -> None:
        """Test datapoint ID generation with empty input."""
        agent_execution = AgentExecution(
            agent_input=None,
            agent_output={},
            agent_trace=[],
        )
        datapoint_id = generate_datapoint_id(agent_execution)

        assert datapoint_id.startswith("datapoint_")
        assert len(datapoint_id.split("_")[-1]) == 8

    def test_generate_datapoint_id_with_string_value(self) -> None:
        """Test datapoint ID generation extracts from any string value."""
        agent_execution = AgentExecution(
            agent_input={"arbitrary_key": "extract this text", "number": 42},
            agent_output={},
            agent_trace=[],
        )
        datapoint_id = generate_datapoint_id(agent_execution)

        assert datapoint_id.startswith("extract_this_text")
        assert len(datapoint_id.split("_")[-1]) == 8

    def test_generate_datapoint_id_no_string_values(self) -> None:
        """Test datapoint ID generation when no string values exist."""
        agent_execution = AgentExecution(
            agent_input={"number": 42, "boolean": True, "nested": {"data": 123}},
            agent_output={},
            agent_trace=[],
        )
        datapoint_id = generate_datapoint_id(agent_execution)

        # Should use first key name since no string values found
        assert datapoint_id.startswith("number_")
        assert len(datapoint_id.split("_")[-1]) == 8

    def test_generate_datapoint_id_empty_string_values(self) -> None:
        """Test datapoint ID generation when string values are empty."""
        agent_execution = AgentExecution(
            agent_input={"empty": "", "whitespace": "   ", "valid": "actual content"},
            agent_output={},
            agent_trace=[],
        )
        datapoint_id = generate_datapoint_id(agent_execution)

        # Should skip empty/whitespace strings and use the valid one
        assert datapoint_id.startswith("actual_content")
        assert len(datapoint_id.split("_")[-1]) == 8

    def test_generate_datapoint_id_consistency(self) -> None:
        """Test that same input generates same datapoint ID."""
        agent_execution1 = AgentExecution(
            agent_input={"user_input": "test query"},
            agent_output={},
            agent_trace=[],
        )
        agent_execution2 = AgentExecution(
            agent_input={"user_input": "test query"},
            agent_output={},
            agent_trace=[],
        )

        datapoint_id1 = generate_datapoint_id(agent_execution1)
        datapoint_id2 = generate_datapoint_id(agent_execution2)

        assert datapoint_id1 == datapoint_id2

    def test_generate_datapoint_id_different_inputs(self) -> None:
        """Test that different inputs generate different datapoint IDs."""
        agent_execution1 = AgentExecution(
            agent_input={"user_input": "first query"},
            agent_output={},
            agent_trace=[],
        )
        agent_execution2 = AgentExecution(
            agent_input={"user_input": "second query"},
            agent_output={},
            agent_trace=[],
        )

        datapoint_id1 = generate_datapoint_id(agent_execution1)
        datapoint_id2 = generate_datapoint_id(agent_execution2)

        assert datapoint_id1 != datapoint_id2


class TestEvaluationResultAggregationLogic:
    """Test evaluation result aggregation with deduplication."""

    def test_aggregate_evaluation_results_empty(self) -> None:
        """Test evaluation result aggregation with empty results."""
        final_score, agg_metrics = calculate_final_score([])

        assert final_score == 0.0
        assert agg_metrics == {}

    def test_aggregate_evaluation_results_single_evaluator(self) -> None:
        """Test evaluation result aggregation with single evaluator across multiple datapoints."""
        results: list[EvaluationResult] = [
            NumericEvaluationResult(
                score=0.8,
                datapoint_id="test1_abc123",
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=1.0,
                datapoint_id="test2_def456",
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=0.6,
                datapoint_id="test3_ghi789",
                evaluator_name="ExactMatchEvaluator",
            ),
        ]

        final_score, agg_metrics = calculate_final_score(results)

        expected_avg = (0.8 + 1.0 + 0.6) / 3  # 0.8
        assert final_score == pytest.approx(expected_avg)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(expected_avg)}

    def test_aggregate_evaluation_results_multiple_evaluators(self) -> None:
        """Test evaluation result aggregation with multiple evaluators."""
        results: list[EvaluationResult] = [
            NumericEvaluationResult(
                score=0.8,
                datapoint_id="test1_abc123",
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=0.9,
                datapoint_id="test1_abc123",
                evaluator_name="ContainsEvaluator",
            ),
            NumericEvaluationResult(
                score=1.0,
                datapoint_id="test2_def456",
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=0.7,
                datapoint_id="test2_def456",
                evaluator_name="ContainsEvaluator",
            ),
        ]

        final_score, agg_metrics = calculate_final_score(results)

        # ExactMatch avg: (0.8 + 1.0) / 2 = 0.9
        # Contains avg: (0.9 + 0.7) / 2 = 0.8
        # Final avg: (0.9 + 0.8) / 2 = 0.85
        assert final_score == pytest.approx(0.85)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.9),
            "ContainsEvaluator": pytest.approx(0.8),
        }

    def test_aggregate_evaluation_results_with_deduplication(self) -> None:
        """Test evaluation result aggregation with duplicate evaluator results on same datapoint."""
        results: list[EvaluationResult] = [
            # Multiple ExactMatch results for same datapoint (should be averaged)
            NumericEvaluationResult(
                score=0.8,
                datapoint_id="test1_abc123",
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=1.0,
                datapoint_id="test1_abc123",
                evaluator_name="ExactMatchEvaluator",  # Duplicate!
            ),
            NumericEvaluationResult(
                score=0.6,
                datapoint_id="test1_abc123",
                evaluator_name="ExactMatchEvaluator",  # Another duplicate!
            ),
            # Single result for different datapoint
            NumericEvaluationResult(
                score=0.5,
                datapoint_id="test2_def456",
                evaluator_name="ExactMatchEvaluator",
            ),
        ]

        final_score, agg_metrics = calculate_final_score(results)

        # datapoint1 ExactMatch avg: (0.8 + 1.0 + 0.6) / 3 = 0.8
        # datapoint2 ExactMatch: 0.5
        # Overall ExactMatch avg: (0.8 + 0.5) / 2 = 0.65
        assert final_score == pytest.approx(0.65)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(0.65)}

    def test_aggregate_evaluation_results_with_weights(self) -> None:
        """Test evaluation result aggregation with evaluator weights."""
        results: list[EvaluationResult] = [
            NumericEvaluationResult(
                score=0.8,
                datapoint_id="test1_abc123",
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=0.6,
                datapoint_id="test1_abc123",
                evaluator_name="ContainsEvaluator",
            ),
        ]

        # Give ExactMatch twice the weight of Contains
        weights = {
            "ExactMatchEvaluator": 2.0,
            "ContainsEvaluator": 1.0,
        }

        final_score, agg_metrics = calculate_final_score(results, weights)

        # Weighted average: (0.8 * 2.0 + 0.6 * 1.0) / (2.0 + 1.0) = 2.2 / 3 = 0.733...
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 1.0) / 3.0
        assert final_score == pytest.approx(expected_weighted_avg)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.8),
            "ContainsEvaluator": pytest.approx(0.6),
        }

    def test_aggregate_evaluation_results_missing_weights(self) -> None:
        """Test evaluation result aggregation when some evaluators are missing from weights dict."""
        results: list[EvaluationResult] = [
            NumericEvaluationResult(
                score=0.8,
                datapoint_id="test1_abc123",
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=0.6,
                datapoint_id="test1_abc123",
                evaluator_name="UnknownEvaluator",  # Not in weights
            ),
        ]

        weights = {"ExactMatchEvaluator": 2.0}  # Missing UnknownEvaluator

        final_score, agg_metrics = calculate_final_score(results, weights)

        # UnknownEvaluator gets default weight of 1.0
        # Weighted average: (0.8 * 2.0 + 0.6 * 1.0) / (2.0 + 1.0) = 2.2 / 3
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 1.0) / 3.0
        assert final_score == pytest.approx(expected_weighted_avg)

    def test_aggregate_evaluation_results_missing_datapoint_id(self) -> None:
        """Test evaluation result aggregation with missing datapoint_id (should use default)."""
        results: list[EvaluationResult] = [
            NumericEvaluationResult(
                score=0.8,
                datapoint_id=None,  # Missing datapoint_id
                evaluator_name="ExactMatchEvaluator",
            ),
            NumericEvaluationResult(
                score=0.6,
                datapoint_id=None,  # Missing datapoint_id
                evaluator_name="ExactMatchEvaluator",
            ),
        ]

        final_score, agg_metrics = calculate_final_score(results)

        # Both should be grouped under "unknown_datapoint" and averaged
        assert final_score == pytest.approx(0.7)  # (0.8 + 0.6) / 2
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(0.7)}

    def test_aggregate_evaluation_results_missing_evaluator_name(self) -> None:
        """Test evaluation result aggregation with missing evaluator_name (should use default)."""
        results: list[EvaluationResult] = [
            NumericEvaluationResult(
                score=0.8,
                datapoint_id="test1_abc123",
                evaluator_name=None,  # Missing evaluator_name
            ),
        ]

        final_score, agg_metrics = calculate_final_score(results)

        assert final_score == pytest.approx(0.8)
        assert agg_metrics == {"unknown_evaluator": pytest.approx(0.8)}

    def test_aggregate_evaluation_results_complex_scenario(self) -> None:
        """Test evaluation result aggregation with complex scenario mimicking the original example."""
        # Scenario:
        # datapoint1: ExactMatch[0.5, 1.0] (avg=0.75), Contains[1.0], ToolCallCount[1.0]
        # datapoint2: ExactMatch[0.0], Contains[1.0]
        # datapoint3: ExactMatch[1.0], ToolCallCount[1.0]
        # Expected per evaluator:
        # ExactMatch: (0.75 + 0.0 + 1.0) / 3 = 0.583
        # Contains: (1.0 + 1.0) / 2 = 1.0
        # ToolCallCount: (1.0 + 1.0) / 2 = 1.0

        results: list[EvaluationResult] = [
            # datapoint1 - multiple ExactMatch results (will be deduplicated)
            NumericEvaluationResult(
                score=0.5, datapoint_id="test1_abc", evaluator_name="ExactMatch"
            ),
            NumericEvaluationResult(
                score=1.0, datapoint_id="test1_abc", evaluator_name="ExactMatch"
            ),
            NumericEvaluationResult(
                score=1.0, datapoint_id="test1_abc", evaluator_name="Contains"
            ),
            NumericEvaluationResult(
                score=1.0, datapoint_id="test1_abc", evaluator_name="ToolCallCount"
            ),
            # datapoint2
            NumericEvaluationResult(
                score=0.0, datapoint_id="test2_def", evaluator_name="ExactMatch"
            ),
            NumericEvaluationResult(
                score=1.0, datapoint_id="test2_def", evaluator_name="Contains"
            ),
            # datapoint3
            NumericEvaluationResult(
                score=1.0, datapoint_id="test3_ghi", evaluator_name="ExactMatch"
            ),
            NumericEvaluationResult(
                score=1.0, datapoint_id="test3_ghi", evaluator_name="ToolCallCount"
            ),
        ]

        final_score, agg_metrics = calculate_final_score(results)

        expected_exact_match = (0.75 + 0.0 + 1.0) / 3  # 0.583
        expected_contains = 1.0
        expected_tool_count = 1.0
        expected_final = (
            expected_exact_match + expected_contains + expected_tool_count
        ) / 3

        assert final_score == pytest.approx(expected_final)
        assert agg_metrics == {
            "ExactMatch": pytest.approx(expected_exact_match),
            "Contains": pytest.approx(expected_contains),
            "ToolCallCount": pytest.approx(expected_tool_count),
        }
