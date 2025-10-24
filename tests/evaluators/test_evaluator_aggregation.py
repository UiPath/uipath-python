"""Test module for evaluation result aggregation logic.

This module tests the deduplication and aggregation functionality
in UiPathEvalOutput.calculate_final_score().
"""

import uuid

import pytest

from uipath._cli._evals._models._output import (
    EvaluationResultDto,
    EvaluationRunResult,
    EvaluationRunResultDto,
    UiPathEvalOutput,
)


class TestEvaluationResultAggregation:
    """Test evaluation result aggregation with deduplication in UiPathEvalOutput."""

    def test_calculate_final_score_empty(self) -> None:
        """Test evaluation result aggregation with empty results."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[],
        )

        final_score, agg_metrics = eval_output.calculate_final_score()

        assert final_score == 0.0
        assert agg_metrics == {}

    def test_calculate_final_score_single_evaluator(self) -> None:
        """Test evaluation result aggregation with single evaluator across multiple datapoints."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.8),
                        )
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test2",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        )
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test3",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.6),
                        )
                    ],
                ),
            ],
        )

        final_score, agg_metrics = eval_output.calculate_final_score()

        expected_avg = (0.8 + 1.0 + 0.6) / 3  # 0.8
        assert final_score == pytest.approx(expected_avg)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(expected_avg)}

    def test_calculate_final_score_multiple_evaluators(self) -> None:
        """Test evaluation result aggregation with multiple evaluators."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.8),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ContainsEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.9),
                        ),
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test2",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ContainsEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.7),
                        ),
                    ],
                ),
            ],
        )

        final_score, agg_metrics = eval_output.calculate_final_score()

        # ExactMatch avg: (0.8 + 1.0) / 2 = 0.9
        # Contains avg: (0.9 + 0.7) / 2 = 0.8
        # Final avg: (0.9 + 0.8) / 2 = 0.85
        assert final_score == pytest.approx(0.85)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.9),
            "ContainsEvaluator": pytest.approx(0.8),
        }

    def test_calculate_final_score_with_deduplication(self) -> None:
        """Test evaluation result aggregation with duplicate evaluator results on same datapoint."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        # Multiple ExactMatch results for same datapoint (should be averaged)
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.8),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",  # Duplicate!
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",  # Another duplicate!
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.6),
                        ),
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test2",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.5),
                        ),
                    ],
                ),
            ],
        )

        final_score, agg_metrics = eval_output.calculate_final_score()

        # datapoint1 ExactMatch avg: (0.8 + 1.0 + 0.6) / 3 = 0.8
        # datapoint2 ExactMatch: 0.5
        # Overall ExactMatch avg: (0.8 + 0.5) / 2 = 0.65
        assert final_score == pytest.approx(0.65)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(0.65)}

    def test_calculate_final_score_with_weights(self) -> None:
        """Test evaluation result aggregation with evaluator weights."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.8),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ContainsEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.6),
                        ),
                    ],
                ),
            ],
        )

        # Give ExactMatch twice the weight of Contains
        weights = {
            "ExactMatchEvaluator": 2.0,
            "ContainsEvaluator": 1.0,
        }

        final_score, agg_metrics = eval_output.calculate_final_score(weights)

        # Weighted average: (0.8 * 2.0 + 0.6 * 1.0) / (2.0 + 1.0) = 2.2 / 3 = 0.733...
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 1.0) / 3.0
        assert final_score == pytest.approx(expected_weighted_avg)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.8),
            "ContainsEvaluator": pytest.approx(0.6),
        }

    def test_calculate_final_score_missing_weights(self) -> None:
        """Test evaluation result aggregation when some evaluators are missing from weights dict."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.8),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="UnknownEvaluator",  # Not in weights
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.6),
                        ),
                    ],
                ),
            ],
        )

        weights = {"ExactMatchEvaluator": 2.0}  # Missing UnknownEvaluator

        final_score, agg_metrics = eval_output.calculate_final_score(weights)

        # UnknownEvaluator gets default weight of 1.0
        # Weighted average: (0.8 * 2.0 + 0.6 * 1.0) / (2.0 + 1.0) = 2.2 / 3
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 1.0) / 3.0
        assert final_score == pytest.approx(expected_weighted_avg)

    def test_calculate_final_score_custom_default_weight(self) -> None:
        """Test evaluation result aggregation with custom default weight."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.8),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="UnknownEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.6),
                        ),
                    ],
                ),
            ],
        )

        weights = {"ExactMatchEvaluator": 2.0}
        default_weight = 0.5  # Custom default weight

        final_score, agg_metrics = eval_output.calculate_final_score(
            weights, default_weight
        )

        # UnknownEvaluator gets default weight of 0.5
        # Weighted average: (0.8 * 2.0 + 0.6 * 0.5) / (2.0 + 0.5) = 1.9 / 2.5 = 0.76
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 0.5) / 2.5
        assert final_score == pytest.approx(expected_weighted_avg)

    def test_calculate_final_score_complex_scenario(self) -> None:
        """Test evaluation result aggregation with complex scenario."""
        # Scenario:
        # datapoint1: ExactMatch[0.5, 1.0] (avg=0.75), Contains[1.0], ToolCallCount[1.0]
        # datapoint2: ExactMatch[0.0], Contains[1.0]
        # datapoint3: ExactMatch[1.0], ToolCallCount[1.0]
        # Expected per evaluator:
        # ExactMatch: (0.75 + 0.0 + 1.0) / 3 = 0.583
        # Contains: (1.0 + 1.0) / 2 = 1.0
        # ToolCallCount: (1.0 + 1.0) / 2 = 1.0

        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatch",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.5),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatch",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="Contains",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ToolCallCount",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test2",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatch",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.0),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="Contains",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test3",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatch",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ToolCallCount",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                    ],
                ),
            ],
        )

        final_score, agg_metrics = eval_output.calculate_final_score()

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

    def test_calculate_final_score_single_datapoint_single_evaluator(self) -> None:
        """Test simplest case: single datapoint, single evaluator."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.85),
                        ),
                    ],
                ),
            ],
        )

        final_score, agg_metrics = eval_output.calculate_final_score()

        assert final_score == pytest.approx(0.85)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(0.85)}

    def test_calculate_final_score_different_evaluators_per_datapoint(self) -> None:
        """Test when different datapoints have different evaluators."""
        eval_output = UiPathEvalOutput(
            evaluation_set_name="test_set",
            evaluation_set_results=[
                EvaluationRunResult(
                    evaluation_name="test1",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.8),
                        ),
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test2",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ContainsEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.9),
                        ),
                    ],
                ),
                EvaluationRunResult(
                    evaluation_name="test3",
                    evaluation_run_results=[
                        EvaluationRunResultDto(
                            evaluator_name="ExactMatchEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=1.0),
                        ),
                        EvaluationRunResultDto(
                            evaluator_name="ContainsEvaluator",
                            evaluator_id=str(uuid.uuid4()),
                            result=EvaluationResultDto(score=0.7),
                        ),
                    ],
                ),
            ],
        )

        final_score, agg_metrics = eval_output.calculate_final_score()

        # ExactMatch: (0.8 + 1.0) / 2 = 0.9 (appears in test1 and test3)
        # Contains: (0.9 + 0.7) / 2 = 0.8 (appears in test2 and test3)
        # Final: (0.9 + 0.8) / 2 = 0.85
        assert final_score == pytest.approx(0.85)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.9),
            "ContainsEvaluator": pytest.approx(0.8),
        }
