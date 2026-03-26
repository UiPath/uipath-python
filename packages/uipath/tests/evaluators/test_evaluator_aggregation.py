"""Test module for evaluation result aggregation logic.

This module tests the compute_evaluator_scores() standalone function,
which handles deduplication, per-evaluator reduction, and weighted scoring.
"""

import uuid
from typing import Any, Callable

import pytest

from uipath.eval.evaluators import ExactMatchEvaluator
from uipath.eval.models.models import EvaluationResultDto
from uipath.eval.runtime._types import (
    UiPathEvalRunResult,
    UiPathEvalRunResultDto,
)
from uipath.eval.runtime.runtime import compute_evaluator_scores


def _make_evaluator(
    name: str, reducer: Callable[[list[EvaluationResultDto]], float] | None = None
) -> Any:
    """Create a minimal mock evaluator with a name and optional custom reduce_scores."""
    _reducer = reducer or (
        lambda results: sum(r.score for r in results) / len(results) if results else 0.0
    )

    class MockEvaluator:
        def reduce_scores(self, results: list[EvaluationResultDto]) -> float:
            return _reducer(results)

    obj = MockEvaluator()
    obj.name = name  # type: ignore[attr-defined]
    return obj


class TestEvaluationResultAggregation:
    """Test evaluation result aggregation with deduplication."""

    def test_compute_evaluator_scores_empty(self) -> None:
        """Test with empty results."""
        final_score, agg_metrics = compute_evaluator_scores([], [])

        assert final_score == 0.0
        assert agg_metrics == {}

    def test_compute_evaluator_scores_single_evaluator(self) -> None:
        """Test with single evaluator across multiple datapoints."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.8),
                    )
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    )
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test3",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.6),
                    )
                ],
            ),
        ]

        evaluators = [_make_evaluator("ExactMatchEvaluator")]
        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

        expected_avg = (0.8 + 1.0 + 0.6) / 3  # 0.8
        assert final_score == pytest.approx(expected_avg)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(expected_avg)}

    def test_compute_evaluator_scores_multiple_evaluators(self) -> None:
        """Test with multiple evaluators."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.8),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ContainsEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.9),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ContainsEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.7),
                    ),
                ],
            ),
        ]

        evaluators = [
            _make_evaluator("ExactMatchEvaluator"),
            _make_evaluator("ContainsEvaluator"),
        ]
        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

        # ExactMatch avg: (0.8 + 1.0) / 2 = 0.9
        # Contains avg: (0.9 + 0.7) / 2 = 0.8
        # Final avg: (0.9 + 0.8) / 2 = 0.85
        assert final_score == pytest.approx(0.85)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.9),
            "ContainsEvaluator": pytest.approx(0.8),
        }

    def test_compute_evaluator_scores_with_deduplication(self) -> None:
        """Test with duplicate evaluator results on same datapoint."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    # Multiple ExactMatch results for same datapoint (should be averaged)
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.8),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",  # Duplicate!
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",  # Another duplicate!
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.6),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.5),
                    ),
                ],
            ),
        ]

        evaluators = [_make_evaluator("ExactMatchEvaluator")]
        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

        # datapoint1 ExactMatch avg: (0.8 + 1.0 + 0.6) / 3 = 0.8
        # datapoint2 ExactMatch: 0.5
        # Overall ExactMatch avg: (0.8 + 0.5) / 2 = 0.65
        assert final_score == pytest.approx(0.65)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(0.65)}

    def test_compute_evaluator_scores_with_weights(self) -> None:
        """Test with evaluator weights."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.8),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ContainsEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.6),
                    ),
                ],
            ),
        ]

        # Give ExactMatch twice the weight of Contains
        weights = {
            "ExactMatchEvaluator": 2.0,
            "ContainsEvaluator": 1.0,
        }

        evaluators = [
            _make_evaluator("ExactMatchEvaluator"),
            _make_evaluator("ContainsEvaluator"),
        ]
        final_score, agg_metrics = compute_evaluator_scores(
            results, evaluators, evaluator_weights=weights
        )

        # Weighted average: (0.8 * 2.0 + 0.6 * 1.0) / (2.0 + 1.0) = 2.2 / 3 = 0.733...
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 1.0) / 3.0
        assert final_score == pytest.approx(expected_weighted_avg)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.8),
            "ContainsEvaluator": pytest.approx(0.6),
        }

    def test_compute_evaluator_scores_missing_weights(self) -> None:
        """Test when some evaluators are missing from weights dict."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.8),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="UnknownEvaluator",  # Not in weights
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.6),
                    ),
                ],
            ),
        ]

        weights = {"ExactMatchEvaluator": 2.0}  # Missing UnknownEvaluator weight

        evaluators = [
            _make_evaluator("ExactMatchEvaluator"),
            _make_evaluator("UnknownEvaluator"),
        ]
        final_score, agg_metrics = compute_evaluator_scores(
            results, evaluators, evaluator_weights=weights
        )

        # UnknownEvaluator gets default weight of 1.0
        # Weighted average: (0.8 * 2.0 + 0.6 * 1.0) / (2.0 + 1.0) = 2.2 / 3
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 1.0) / 3.0
        assert final_score == pytest.approx(expected_weighted_avg)

    def test_compute_evaluator_scores_custom_default_weight(self) -> None:
        """Test with custom default weight."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.8),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="UnknownEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.6),
                    ),
                ],
            ),
        ]

        weights = {"ExactMatchEvaluator": 2.0}
        default_weight = 0.5  # Custom default weight

        evaluators = [
            _make_evaluator("ExactMatchEvaluator"),
            _make_evaluator("UnknownEvaluator"),
        ]
        final_score, agg_metrics = compute_evaluator_scores(
            results,
            evaluators,
            evaluator_weights=weights,
            default_weight=default_weight,
        )

        # UnknownEvaluator gets default weight of 0.5
        # Weighted average: (0.8 * 2.0 + 0.6 * 0.5) / (2.0 + 0.5) = 1.9 / 2.5 = 0.76
        expected_weighted_avg = (0.8 * 2.0 + 0.6 * 0.5) / 2.5
        assert final_score == pytest.approx(expected_weighted_avg)

    def test_compute_evaluator_scores_complex_scenario(self) -> None:
        """Test complex scenario with dedup, multiple evaluators, and multiple datapoints."""
        # Scenario:
        # datapoint1: ExactMatch[0.5, 1.0] (avg=0.75), Contains[1.0], ToolCallCount[1.0]
        # datapoint2: ExactMatch[0.0], Contains[1.0]
        # datapoint3: ExactMatch[1.0], ToolCallCount[1.0]
        # Expected per evaluator:
        # ExactMatch: (0.75 + 0.0 + 1.0) / 3 = 0.583
        # Contains: (1.0 + 1.0) / 2 = 1.0
        # ToolCallCount: (1.0 + 1.0) / 2 = 1.0

        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatch",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.5),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatch",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="Contains",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ToolCallCount",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatch",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="Contains",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test3",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatch",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ToolCallCount",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                ],
            ),
        ]

        evaluators = [
            _make_evaluator("ExactMatch"),
            _make_evaluator("Contains"),
            _make_evaluator("ToolCallCount"),
        ]
        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

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

    def test_compute_evaluator_scores_single_datapoint_single_evaluator(self) -> None:
        """Test simplest case: single datapoint, single evaluator."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.85),
                    ),
                ],
            ),
        ]

        evaluators = [_make_evaluator("ExactMatchEvaluator")]
        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

        assert final_score == pytest.approx(0.85)
        assert agg_metrics == {"ExactMatchEvaluator": pytest.approx(0.85)}

    def test_compute_evaluator_scores_different_evaluators_per_datapoint(self) -> None:
        """Test when different datapoints have different evaluators."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.8),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ContainsEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.9),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test3",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="ExactMatchEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="ContainsEvaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.7),
                    ),
                ],
            ),
        ]

        evaluators = [
            _make_evaluator("ExactMatchEvaluator"),
            _make_evaluator("ContainsEvaluator"),
        ]
        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

        # ExactMatch: (0.8 + 1.0) / 2 = 0.9 (appears in test1 and test3)
        # Contains: (0.9 + 0.7) / 2 = 0.8 (appears in test2 and test3)
        # Final: (0.9 + 0.8) / 2 = 0.85
        assert final_score == pytest.approx(0.85)
        assert agg_metrics == {
            "ExactMatchEvaluator": pytest.approx(0.9),
            "ContainsEvaluator": pytest.approx(0.8),
        }


class TestBaseEvaluatorReduceScores:
    """Test the default reduce_scores method on GenericBaseEvaluator."""

    @pytest.fixture()
    def evaluator(self) -> Any:
        """Create a minimal ExactMatchEvaluator for testing reduce_scores."""
        return ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {}, "id": str(uuid.uuid4())}
        )

    def test_reduce_scores_default_average(self, evaluator: Any) -> None:
        """Default reduce_scores computes simple average."""
        results = [
            EvaluationResultDto(score=0.8),
            EvaluationResultDto(score=1.0),
            EvaluationResultDto(score=0.6),
        ]
        assert evaluator.reduce_scores(results) == pytest.approx(0.8)

    def test_reduce_scores_empty_list(self, evaluator: Any) -> None:
        """Default reduce_scores returns 0.0 for empty list."""
        assert evaluator.reduce_scores([]) == 0.0

    def test_reduce_scores_single_score(self, evaluator: Any) -> None:
        """Default reduce_scores returns the single score."""
        assert evaluator.reduce_scores(
            [EvaluationResultDto(score=0.75)]
        ) == pytest.approx(0.75)

    def test_reduce_scores_all_zeros(self, evaluator: Any) -> None:
        """Default reduce_scores with all zeros."""
        results = [
            EvaluationResultDto(score=0.0),
            EvaluationResultDto(score=0.0),
            EvaluationResultDto(score=0.0),
        ]
        assert evaluator.reduce_scores(results) == 0.0

    def test_reduce_scores_all_ones(self, evaluator: Any) -> None:
        """Default reduce_scores with all ones."""
        results = [
            EvaluationResultDto(score=1.0),
            EvaluationResultDto(score=1.0),
            EvaluationResultDto(score=1.0),
        ]
        assert evaluator.reduce_scores(results) == 1.0


class TestCustomReducerIntegration:
    """Test that compute_evaluator_scores uses evaluator reduce_scores correctly."""

    def test_uses_evaluator_reducer(self) -> None:
        """Test that an evaluator's reduce_scores is used instead of default average."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="MyEvaluator",
                        evaluator_id="my-eval",
                        result=EvaluationResultDto(score=0.5),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="MyEvaluator",
                        evaluator_id="my-eval",
                        result=EvaluationResultDto(score=1.0),
                    ),
                ],
            ),
        ]

        # Custom reducer: sum instead of average
        evaluators = [
            _make_evaluator(
                "MyEvaluator", lambda results: sum(r.score for r in results)
            )
        ]

        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

        # sum([0.5, 1.0]) = 1.5, not average 0.75
        assert agg_metrics == {"MyEvaluator": pytest.approx(1.5)}
        assert final_score == pytest.approx(1.5)

    def test_missing_evaluator_raises_error(self) -> None:
        """Test that a missing evaluator raises a clear ValueError."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="UnknownEval",
                        evaluator_id="unknown-type",
                        result=EvaluationResultDto(score=0.4),
                    ),
                ],
            ),
        ]

        with pytest.raises(ValueError, match="UnknownEval"):
            compute_evaluator_scores(results, [])

    def test_details_passed_to_reducer(self) -> None:
        """Test that EvaluationResultDto.details are passed through to reduce_scores."""
        captured_details: list[dict[str, Any] | str | None] = []

        def capturing_reducer(results: list[EvaluationResultDto]) -> float:
            for r in results:
                captured_details.append(r.details)
            return sum(r.score for r in results) / len(results) if results else 0.0

        details_a = {"predicted": "cat", "expected": "dog"}
        details_b = {"predicted": "cat", "expected": "cat"}

        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="MyEval",
                        evaluator_id="my-eval",
                        result=EvaluationResultDto(score=0.0, details=details_a),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="MyEval",
                        evaluator_id="my-eval",
                        result=EvaluationResultDto(score=1.0, details=details_b),
                    ),
                ],
            ),
        ]

        evaluators = [_make_evaluator("MyEval", capturing_reducer)]
        compute_evaluator_scores(results, evaluators)

        assert len(captured_details) == 2
        assert captured_details[0] == {"predicted": "cat", "expected": "dog"}
        assert captured_details[1] == {"predicted": "cat", "expected": "cat"}

    def test_mixed_custom_and_default_reducers(self) -> None:
        """Test with one custom reducer and one falling back to default."""
        results = [
            UiPathEvalRunResult(
                evaluation_name="test1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="CustomEval",
                        evaluator_id="custom-type",
                        result=EvaluationResultDto(score=0.8),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="DefaultEval",
                        evaluator_id="default-type",
                        result=EvaluationResultDto(score=0.6),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="test2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="CustomEval",
                        evaluator_id="custom-type",
                        result=EvaluationResultDto(score=1.0),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="DefaultEval",
                        evaluator_id="default-type",
                        result=EvaluationResultDto(score=0.4),
                    ),
                ],
            ),
        ]

        # CustomEval uses min, DefaultEval uses default average
        evaluators = [
            _make_evaluator(
                "CustomEval", lambda results: min(r.score for r in results)
            ),
            _make_evaluator("DefaultEval"),
        ]

        final_score, agg_metrics = compute_evaluator_scores(results, evaluators)

        # CustomEval: min([0.8, 1.0]) = 0.8
        # DefaultEval: avg([0.6, 0.4]) = 0.5
        # Final: (0.8 + 0.5) / 2 = 0.65
        assert agg_metrics == {
            "CustomEval": pytest.approx(0.8),
            "DefaultEval": pytest.approx(0.5),
        }
        assert final_score == pytest.approx(0.65)


class TestBinaryClassificationReduceScores:
    """Test BinaryClassificationEvaluator.reduce_scores for precision/recall/f-score."""

    def _make_binary_evaluator(
        self,
        metric_type: str = "precision",
        f_value: float = 1.0,
    ):
        from uipath.eval.evaluators.binary_classification_evaluator import (
            BinaryClassificationEvaluator,
        )

        config = {
            "name": "BinaryTest",
            "target_output_key": "class",
            "positive_class": "spam",
            "metric_type": metric_type,
            "f_value": f_value,
        }
        return BinaryClassificationEvaluator.model_validate(
            {"evaluatorConfig": config, "id": "binary-test"}
        )

    def _dp(self, predicted: str, expected: str) -> EvaluationResultDto:
        """Create a EvaluationResultDto with BaseEvaluatorJustification."""
        from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification

        score = 1.0 if predicted == expected else 0.0
        return EvaluationResultDto(
            score=score,
            details=BaseEvaluatorJustification(
                expected=expected,
                actual=predicted,
            ).model_dump(),
        )

    def test_binary_precision(self) -> None:
        """2 TP + 1 FP + 1 FN + 1 TN → precision = 2/(2+1) = 2/3."""
        evaluator = self._make_binary_evaluator("precision")
        results = [
            self._dp("spam", "spam"),  # TP
            self._dp("spam", "spam"),  # TP
            self._dp("spam", "ham"),  # FP
            self._dp("ham", "spam"),  # FN
            self._dp("ham", "ham"),  # TN
        ]
        assert evaluator.reduce_scores(results) == pytest.approx(2 / 3)

    def test_binary_recall(self) -> None:
        """2 TP + 1 FP + 1 FN + 1 TN → recall = 2/(2+1) = 2/3."""
        evaluator = self._make_binary_evaluator("recall")
        results = [
            self._dp("spam", "spam"),
            self._dp("spam", "spam"),
            self._dp("spam", "ham"),
            self._dp("ham", "spam"),
            self._dp("ham", "ham"),
        ]
        assert evaluator.reduce_scores(results) == pytest.approx(2 / 3)

    def test_binary_f1(self) -> None:
        """2 TP + 1 FP + 1 FN → P=R=2/3, F1 = 2*P*R/(P+R) = 2/3."""
        evaluator = self._make_binary_evaluator("f-score", f_value=1.0)
        results = [
            self._dp("spam", "spam"),
            self._dp("spam", "spam"),
            self._dp("spam", "ham"),
            self._dp("ham", "spam"),
            self._dp("ham", "ham"),
        ]
        p = 2 / 3
        r = 2 / 3
        expected_f1 = 2 * p * r / (p + r)
        assert evaluator.reduce_scores(results) == pytest.approx(expected_f1)

    def test_binary_f2(self) -> None:
        """F2 weights recall more: (1+4)*P*R / (4*P+R)."""
        evaluator = self._make_binary_evaluator("f-score", f_value=2.0)
        # 3 TP, 1 FP, 2 FN → P=3/4, R=3/5
        results = [
            self._dp("spam", "spam"),  # TP
            self._dp("spam", "spam"),  # TP
            self._dp("spam", "spam"),  # TP
            self._dp("spam", "ham"),  # FP
            self._dp("ham", "spam"),  # FN
            self._dp("ham", "spam"),  # FN
        ]
        p = 3 / 4
        r = 3 / 5
        beta_sq = 4.0
        expected = (1 + beta_sq) * p * r / (beta_sq * p + r)
        assert evaluator.reduce_scores(results) == pytest.approx(expected)

    def test_binary_precision_no_positive_predictions(self) -> None:
        """No positive predictions → precision = 0."""
        evaluator = self._make_binary_evaluator("precision")
        results = [
            self._dp("ham", "spam"),  # FN
            self._dp("ham", "spam"),  # FN
            self._dp("ham", "ham"),  # TN
            self._dp("ham", "ham"),  # TN
        ]
        assert evaluator.reduce_scores(results) == 0.0

    def test_binary_recall_no_positive_expected(self) -> None:
        """No positive expected → recall = 0."""
        evaluator = self._make_binary_evaluator("recall")
        results = [
            self._dp("spam", "ham"),  # FP
            self._dp("spam", "ham"),  # FP
            self._dp("ham", "ham"),  # TN
            self._dp("ham", "ham"),  # TN
        ]
        assert evaluator.reduce_scores(results) == 0.0

    def test_binary_empty_scores(self) -> None:
        """Empty results returns 0."""
        evaluator = self._make_binary_evaluator("precision")
        assert evaluator.reduce_scores([]) == 0.0

    def test_binary_perfect_precision(self) -> None:
        """All TP, no FP → precision = 1.0."""
        evaluator = self._make_binary_evaluator("precision")
        results = [
            self._dp("spam", "spam"),
            self._dp("spam", "spam"),
            self._dp("spam", "spam"),
        ]
        assert evaluator.reduce_scores(results) == 1.0


class TestMulticlassClassificationReduceScores:
    """Test MulticlassClassificationEvaluator.reduce_scores for micro/macro metrics."""

    def _make_multiclass_evaluator(
        self,
        classes: list[str],
        metric_type: str = "precision",
        averaging: str = "macro",
        f_value: float = 1.0,
    ):
        from uipath.eval.evaluators.multiclass_classification_evaluator import (
            MulticlassClassificationEvaluator,
        )

        config = {
            "name": "MulticlassTest",
            "target_output_key": "class",
            "classes": classes,
            "metric_type": metric_type,
            "averaging": averaging,
            "f_value": f_value,
        }
        return MulticlassClassificationEvaluator.model_validate(
            {"evaluatorConfig": config, "id": "multiclass-test"}
        )

    def _dp(self, predicted: str, expected: str) -> EvaluationResultDto:
        """Create a EvaluationResultDto with BaseEvaluatorJustification."""
        from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification

        score = 1.0 if predicted == expected else 0.0
        return EvaluationResultDto(
            score=score,
            details=BaseEvaluatorJustification(
                expected=expected,
                actual=predicted,
            ).model_dump(),
        )

    def test_multiclass_macro_precision_perfect(self) -> None:
        """All correct predictions → macro precision = 1.0."""
        classes = ["cat", "dog", "bird"]
        evaluator = self._make_multiclass_evaluator(classes, "precision", "macro")
        results = [
            self._dp("cat", "cat"),
            self._dp("dog", "dog"),
            self._dp("bird", "bird"),
        ]
        assert evaluator.reduce_scores(results) == pytest.approx(1.0)

    def test_multiclass_macro_precision_known_confusion(self) -> None:
        """Known confusion matrix → verify macro precision.

        classes: [a, b, c]
        Confusion matrix (confusion[pred][exp]):
          pred a: [2, 1, 0]  → TP_a=2, FP_a=1
          pred b: [0, 3, 1]  → TP_b=3, FP_b=1
          pred c: [1, 0, 2]  → TP_c=2, FP_c=1

        Precision: a=2/3, b=3/4, c=2/3
        Macro precision = (2/3 + 3/4 + 2/3) / 3
        """
        classes = ["a", "b", "c"]
        evaluator = self._make_multiclass_evaluator(classes, "precision", "macro")
        results = [
            # pred=a, exp=a (TP for a) ×2
            self._dp("a", "a"),
            self._dp("a", "a"),
            # pred=a, exp=b (FP for a) ×1
            self._dp("a", "b"),
            # pred=b, exp=b (TP for b) ×3
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            # pred=b, exp=c (FP for b) ×1
            self._dp("b", "c"),
            # pred=c, exp=a (FP for c) ×1
            self._dp("c", "a"),
            # pred=c, exp=c (TP for c) ×2
            self._dp("c", "c"),
            self._dp("c", "c"),
        ]
        expected = (2 / 3 + 3 / 4 + 2 / 3) / 3
        assert evaluator.reduce_scores(results) == pytest.approx(expected)

    def test_multiclass_macro_recall_known_confusion(self) -> None:
        """Same confusion matrix, test macro recall.

        Recall: a=2/(2+1)=2/3, b=3/(3+1)=3/4, c=2/(2+1)=2/3
        Macro recall = (2/3 + 3/4 + 2/3) / 3
        """
        classes = ["a", "b", "c"]
        evaluator = self._make_multiclass_evaluator(classes, "recall", "macro")
        results = [
            self._dp("a", "a"),
            self._dp("a", "a"),
            self._dp("a", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "c"),
            self._dp("c", "a"),
            self._dp("c", "c"),
            self._dp("c", "c"),
        ]
        expected = (2 / 3 + 3 / 4 + 2 / 3) / 3
        assert evaluator.reduce_scores(results) == pytest.approx(expected)

    def test_multiclass_micro_precision_known_confusion(self) -> None:
        """Micro precision: global TP / (global TP + global FP).

        Total TP = 2+3+2 = 7, Total FP = 1+1+1 = 3
        Micro precision = 7/10 = 0.7
        """
        classes = ["a", "b", "c"]
        evaluator = self._make_multiclass_evaluator(classes, "precision", "micro")
        results = [
            self._dp("a", "a"),
            self._dp("a", "a"),
            self._dp("a", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "c"),
            self._dp("c", "a"),
            self._dp("c", "c"),
            self._dp("c", "c"),
        ]
        assert evaluator.reduce_scores(results) == pytest.approx(7 / 10)

    def test_multiclass_micro_recall_known_confusion(self) -> None:
        """Micro recall: global TP / (global TP + global FN).

        Total TP = 7, Total FN = 1+1+1 = 3
        Micro recall = 7/10 = 0.7
        """
        classes = ["a", "b", "c"]
        evaluator = self._make_multiclass_evaluator(classes, "recall", "micro")
        results = [
            self._dp("a", "a"),
            self._dp("a", "a"),
            self._dp("a", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "c"),
            self._dp("c", "a"),
            self._dp("c", "c"),
            self._dp("c", "c"),
        ]
        assert evaluator.reduce_scores(results) == pytest.approx(7 / 10)

    def test_multiclass_micro_f1(self) -> None:
        """Micro F1 with the same data. Since micro P = micro R = 0.7, F1 = 0.7."""
        classes = ["a", "b", "c"]
        evaluator = self._make_multiclass_evaluator(
            classes, "f-score", "micro", f_value=1.0
        )
        results = [
            self._dp("a", "a"),
            self._dp("a", "a"),
            self._dp("a", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "c"),
            self._dp("c", "a"),
            self._dp("c", "c"),
            self._dp("c", "c"),
        ]
        assert evaluator.reduce_scores(results) == pytest.approx(0.7)

    def test_multiclass_macro_f1(self) -> None:
        """Macro F1 from per-class F1 values."""
        classes = ["a", "b", "c"]
        evaluator = self._make_multiclass_evaluator(
            classes, "f-score", "macro", f_value=1.0
        )
        results = [
            self._dp("a", "a"),
            self._dp("a", "a"),
            self._dp("a", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "b"),
            self._dp("b", "c"),
            self._dp("c", "a"),
            self._dp("c", "c"),
            self._dp("c", "c"),
        ]
        # Per-class: P_a=R_a=2/3→F1_a=2/3, P_b=R_b=3/4→F1_b=3/4, P_c=R_c=2/3→F1_c=2/3
        expected = (2 / 3 + 3 / 4 + 2 / 3) / 3
        assert evaluator.reduce_scores(results) == pytest.approx(expected)

    def test_multiclass_empty_scores(self) -> None:
        """Empty results returns 0."""
        evaluator = self._make_multiclass_evaluator(["a", "b"], "precision", "macro")
        assert evaluator.reduce_scores([]) == 0.0

    def test_multiclass_two_classes(self) -> None:
        """Binary-like scenario with 2 classes via multiclass evaluator.

        classes: [pos, neg]
        2 TP, 1 FP, 1 FN → precision_pos=2/3, precision_neg=1/2
        Macro precision = (2/3 + 1/2) / 2
        """
        classes = ["pos", "neg"]
        evaluator = self._make_multiclass_evaluator(classes, "precision", "macro")
        results = [
            self._dp("pos", "pos"),  # TP for pos
            self._dp("pos", "pos"),  # TP for pos
            self._dp("pos", "neg"),  # FP for pos
            self._dp("neg", "pos"),  # FN for pos
            self._dp("neg", "neg"),  # TN for pos / TP for neg
        ]
        # confusion: pred_pos=[2, 1], pred_neg=[1, 1]
        # P_pos = 2/3, P_neg = 1/2
        expected = (2 / 3 + 1 / 2) / 2
        assert evaluator.reduce_scores(results) == pytest.approx(expected)
