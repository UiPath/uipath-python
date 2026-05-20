"""Tests for dataset-level classification evaluators (Precision, Recall, FScore).

Covers the math (2-class, 3-class, micro vs macro, F-beta), edge cases
(empty input, out-of-vocab labels, malformed details), and runtime-level
routing where compute_dataset_evaluator_results selects results by name.
"""

import uuid

import pytest

from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification
from uipath.eval.evaluators.classification_dataset_evaluators import (
    ClassificationDetails,
    FScoreDatasetEvaluator,
    FScoreDatasetEvaluatorConfig,
    PrecisionDatasetEvaluator,
    PrecisionDatasetEvaluatorConfig,
    RecallDatasetEvaluator,
    RecallDatasetEvaluatorConfig,
)
from uipath.eval.evaluators.dataset_evaluator_factory import build_dataset_evaluator
from uipath.eval.models.models import (
    EvaluationResultDto,
    EvaluatorType,
    NumericEvaluationResult,
)
from uipath.eval.runtime._types import (
    UiPathEvalRunResult,
    UiPathEvalRunResultDto,
)
from uipath.eval.runtime.runtime import compute_dataset_evaluator_results


def _result(
    expected: str, actual: str, score: float | None = None
) -> EvaluationResultDto:
    """Build an EvaluationResultDto carrying an expected/actual justification."""
    if score is None:
        score = 1.0 if expected.lower() == actual.lower() else 0.0
    justification = BaseEvaluatorJustification(expected=expected, actual=actual)
    return EvaluationResultDto(
        score=score,
        details=justification.model_dump(),
    )


def _precision(classes: list[str], average: str = "macro") -> PrecisionDatasetEvaluator:
    return PrecisionDatasetEvaluator(
        PrecisionDatasetEvaluatorConfig(
            id="p1",
            name="precision",
            source_evaluator="intent_match",
            classes=classes,
            average=average,  # type: ignore[arg-type]
        )
    )


def _recall(classes: list[str], average: str = "macro") -> RecallDatasetEvaluator:
    return RecallDatasetEvaluator(
        RecallDatasetEvaluatorConfig(
            id="r1",
            name="recall",
            source_evaluator="intent_match",
            classes=classes,
            average=average,  # type: ignore[arg-type]
        )
    )


def _fscore(
    classes: list[str], average: str = "macro", f_value: float = 1.0
) -> FScoreDatasetEvaluator:
    return FScoreDatasetEvaluator(
        FScoreDatasetEvaluatorConfig(
            id="f1",
            name="fscore",
            source_evaluator="intent_match",
            classes=classes,
            average=average,  # type: ignore[arg-type]
            f_value=f_value,
        )
    )


def _details(result: NumericEvaluationResult) -> ClassificationDetails:
    """Type-narrowing helper for asserting on details."""
    assert isinstance(result.details, ClassificationDetails)
    return result.details


class TestPrecisionEvaluator:
    def test_empty_input_returns_zeroed_result(self) -> None:
        result = _precision(["cat", "dog"]).evaluate([])
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0
        d = _details(result)
        assert d.n_total == 0 and d.n_scored == 0
        assert d.confusion_matrix == [[0, 0], [0, 0]]
        assert d.per_class["cat"].tp == 0
        assert d.per_class["cat"].tn == 0

    def test_two_class_macro(self) -> None:
        # 4 datapoints: 2 TP_yes, 1 FN_yes (predicted no), 1 FP_yes (predicted yes when expected no).
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("yes", "no"),  # FN for yes, FP for no
            _result("no", "yes"),  # FP for yes, FN for no
        ]
        result = _precision(["yes", "no"], average="macro").evaluate(results)
        d = _details(result)
        # precision_yes = 2 / (2 + 1) = 2/3
        # precision_no  = 0 / (0 + 1) = 0
        # macro = (2/3 + 0) / 2 = 1/3
        assert d.per_class["yes"].value == pytest.approx(2 / 3)
        assert d.per_class["no"].value == pytest.approx(0.0)
        assert d.macro == pytest.approx((2 / 3 + 0.0) / 2)
        assert result.score == pytest.approx(d.macro)

    def test_two_class_micro_equals_accuracy(self) -> None:
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("yes", "no"),
            _result("no", "yes"),
        ]
        result = _precision(["yes", "no"], average="micro").evaluate(results)
        d = _details(result)
        # micro precision = sum(TP) / sum(TP + FP)
        # sum(TP) = 2 (yes diag) + 0 (no diag) = 2
        # sum(FP) = 1 (yes off-diag row) + 1 (no off-diag row) = 2
        # micro = 2 / (2 + 2) = 0.5 — equals accuracy 2/4 in the 2-class case
        assert d.micro == pytest.approx(0.5)
        assert result.score == pytest.approx(0.5)

    def test_three_class_macro(self) -> None:
        # Each class gets 2 TP, 1 FP, 1 FN — symmetric setup
        pairs = [
            ("cat", "cat"),
            ("cat", "cat"),
            ("cat", "dog"),  # FN_cat, FP_dog
            ("dog", "dog"),
            ("dog", "dog"),
            ("dog", "bird"),  # FN_dog, FP_bird
            ("bird", "bird"),
            ("bird", "bird"),
            ("bird", "cat"),  # FN_bird, FP_cat
        ]
        result = _precision(["cat", "dog", "bird"], average="macro").evaluate(
            [_result(e, a) for e, a in pairs]
        )
        d = _details(result)
        # per-class precision = 2 / (2 + 1) = 2/3 for all three
        for label in ("cat", "dog", "bird"):
            m = d.per_class[label]
            assert m.tp == 2 and m.fp == 1 and m.fn == 1 and m.tn == 5
            assert m.value == pytest.approx(2 / 3)
        assert d.macro == pytest.approx(2 / 3)
        assert result.score == pytest.approx(2 / 3)


class TestRecallEvaluator:
    def test_two_class_macro(self) -> None:
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("yes", "no"),
            _result("no", "yes"),
        ]
        result = _recall(["yes", "no"], average="macro").evaluate(results)
        d = _details(result)
        # recall_yes = TP / (TP + FN) = 2 / (2 + 1) = 2/3
        # recall_no  = 0 / (0 + 1) = 0
        # macro = 1/3
        assert d.per_class["yes"].value == pytest.approx(2 / 3)
        assert d.per_class["no"].value == pytest.approx(0.0)
        assert result.score == pytest.approx(1 / 3)

    def test_recall_differs_from_precision(self) -> None:
        # Asymmetric example so precision != recall.
        results = [
            _result("yes", "yes"),  # TP
            _result("yes", "yes"),  # TP
            _result("no", "yes"),  # FP for yes
            _result("no", "yes"),  # FP for yes
            _result("no", "no"),  # TP for no
        ]
        p = _details(_precision(["yes", "no"], average="macro").evaluate(results))
        r = _details(_recall(["yes", "no"], average="macro").evaluate(results))
        # precision_yes = 2/(2+2)=0.5, precision_no = 1/(1+0)=1.0
        assert p.per_class["yes"].value == pytest.approx(0.5)
        assert p.per_class["no"].value == pytest.approx(1.0)
        # recall_yes = 2/(2+0)=1.0, recall_no = 1/(1+2)=1/3
        assert r.per_class["yes"].value == pytest.approx(1.0)
        assert r.per_class["no"].value == pytest.approx(1 / 3)


class TestFScoreEvaluator:
    def test_f1_equals_harmonic_mean_of_p_and_r(self) -> None:
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("yes", "no"),
            _result("no", "yes"),
        ]
        f = _details(
            _fscore(["yes", "no"], average="macro", f_value=1.0).evaluate(results)
        )
        # precision_yes = 2/3, recall_yes = 2/3 -> F1_yes = 2/3
        # precision_no  = 0,   recall_no  = 0    -> F1_no  = 0
        assert f.per_class["yes"].value == pytest.approx(2 / 3)
        assert f.per_class["no"].value == pytest.approx(0.0)
        assert f.macro == pytest.approx((2 / 3 + 0.0) / 2)

    def test_f_beta_emphasizes_recall_when_beta_above_one(self) -> None:
        # Asymmetric setup: precision_yes = 0.5, recall_yes = 1.0.
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("no", "yes"),
            _result("no", "yes"),
            _result("no", "no"),
        ]
        f1 = _details(
            _fscore(["yes", "no"], average="macro", f_value=1.0).evaluate(results)
        )
        f2 = _details(
            _fscore(["yes", "no"], average="macro", f_value=2.0).evaluate(results)
        )
        # F_beta with beta>1 weighs recall higher. Since recall_yes > precision_yes,
        # F2_yes should be > F1_yes.
        assert f2.per_class["yes"].value > f1.per_class["yes"].value

    def test_three_class_micro_pools_across_classes(self) -> None:
        # Same symmetric setup as the precision macro test.
        pairs = [
            ("cat", "cat"),
            ("cat", "cat"),
            ("cat", "dog"),
            ("dog", "dog"),
            ("dog", "dog"),
            ("dog", "bird"),
            ("bird", "bird"),
            ("bird", "bird"),
            ("bird", "cat"),
        ]
        d = _details(
            _fscore(["cat", "dog", "bird"], average="micro", f_value=1.0).evaluate(
                [_result(e, a) for e, a in pairs]
            )
        )
        # micro precision == micro recall == 6/9 (accuracy when each off-diag
        # contributes once to FP and once to FN globally). micro F1 = 6/9.
        assert d.micro == pytest.approx(6 / 9)


class TestSkippingAndEdgeCases:
    def test_out_of_vocab_labels_are_skipped(self) -> None:
        results = [
            _result("cat", "cat"),
            _result("cat", "platypus"),  # actual not in classes
            _result("zebra", "dog"),  # expected not in classes
        ]
        d = _details(_precision(["cat", "dog"]).evaluate(results))
        assert d.n_total == 3 and d.n_scored == 1 and d.n_skipped == 2

    def test_results_without_justification_are_skipped(self) -> None:
        results = [
            _result("cat", "cat"),
            EvaluationResultDto(score=1.0, details="just a string"),
            EvaluationResultDto(score=0.0, details={"unrelated": "shape"}),
        ]
        d = _details(_precision(["cat", "dog"]).evaluate(results))
        assert d.n_total == 3 and d.n_scored == 1 and d.n_skipped == 2

    def test_case_insensitive_by_default(self) -> None:
        results = [_result("Cat", "CAT"), _result("DOG", "dog")]
        d = _details(_precision(["cat", "dog"]).evaluate(results))
        assert d.per_class["cat"].tp == 1
        assert d.per_class["dog"].tp == 1


class TestFactory:
    def test_builds_evaluator_from_dict(self) -> None:
        config_data = {
            "id": "precision_intent",
            "name": "precision_intent",
            "type": EvaluatorType.DATASET_PRECISION.value,
            "sourceEvaluator": "intent_match",
            "classes": ["yes", "no"],
            "average": "macro",
        }
        evaluator = build_dataset_evaluator(config_data)
        assert isinstance(evaluator, PrecisionDatasetEvaluator)
        assert evaluator.source_evaluator == "intent_match"
        assert evaluator.name == "precision_intent"

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown dataset evaluator type"):
            build_dataset_evaluator(
                {
                    "id": "x",
                    "name": "x",
                    "type": "uipath-not-a-thing",
                    "sourceEvaluator": "intent_match",
                    "classes": ["yes", "no"],
                }
            )

    def test_missing_type_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required field 'type'"):
            build_dataset_evaluator(
                {
                    "id": "x",
                    "name": "x",
                    "sourceEvaluator": "intent_match",
                    "classes": ["yes", "no"],
                }
            )


class TestComputeDatasetEvaluatorResults:
    """End-to-end: dataset evaluator picks results by source_evaluator name."""

    def test_routes_to_correct_source_and_ignores_others(self) -> None:
        eval_results = [
            UiPathEvalRunResult(
                evaluation_name="dp1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="intent_match",
                        evaluator_id=str(uuid.uuid4()),
                        result=_result("yes", "yes"),
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="some_other_evaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.5),
                    ),
                ],
            ),
            UiPathEvalRunResult(
                evaluation_name="dp2",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="intent_match",
                        evaluator_id=str(uuid.uuid4()),
                        result=_result("yes", "no"),
                    ),
                ],
            ),
        ]

        out = compute_dataset_evaluator_results(
            eval_results, [_precision(["yes", "no"], average="macro")]
        )
        assert set(out) == {"precision"}
        dto = out["precision"]
        assert isinstance(dto, EvaluationResultDto)
        # The unrelated 0.5 score from some_other_evaluator must NOT be in the
        # matrix — only the two intent_match results count.
        assert isinstance(dto.details, dict)
        assert dto.details["n_scored"] == 2

    def test_line_by_line_subresults_are_excluded(self) -> None:
        eval_results = [
            UiPathEvalRunResult(
                evaluation_name="dp1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="intent_match",
                        evaluator_id=str(uuid.uuid4()),
                        result=_result("yes", "yes"),
                        is_line_result=True,
                    ),
                    UiPathEvalRunResultDto(
                        evaluator_name="intent_match",
                        evaluator_id=str(uuid.uuid4()),
                        result=_result("no", "no"),
                    ),
                ],
            ),
        ]
        out = compute_dataset_evaluator_results(
            eval_results, [_precision(["yes", "no"])]
        )
        assert isinstance(out["precision"].details, dict)
        assert out["precision"].details["n_scored"] == 1

    def test_source_with_no_results_produces_zeroed_report(self) -> None:
        eval_results = [
            UiPathEvalRunResult(
                evaluation_name="dp1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="some_other_evaluator",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=1.0),
                    ),
                ],
            ),
        ]
        out = compute_dataset_evaluator_results(
            eval_results, [_precision(["yes", "no"])]
        )
        dto = out["precision"]
        assert dto.score == 0.0
        assert isinstance(dto.details, dict)
        assert dto.details["n_scored"] == 0
