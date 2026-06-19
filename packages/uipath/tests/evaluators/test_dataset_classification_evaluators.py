"""Tests for dataset-level classification evaluators (Precision, Recall, FScore).

Covers the math (2-class, 3-class, micro vs macro, F-beta), edge cases
(empty input, out-of-vocab labels, malformed details), factory dispatch, and
runtime-level routing where compute_dataset_evaluator_results walks
per-datapoint evaluator configs' embedded ``aggregators`` lists.
"""

import uuid

import pytest
from pydantic import BaseModel

from uipath.eval.evaluators._aggregator_specs import (
    FScoreAggregatorSpec,
    PrecisionAggregatorSpec,
    RecallAggregatorSpec,
)
from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification
from uipath.eval.evaluators.classification_dataset_evaluators import (
    ClassificationDatasetEvaluator,
    ClassificationDetails,
)
from uipath.eval.evaluators.dataset_evaluator_factory import build_dataset_evaluator
from uipath.eval.evaluators.multiclass_classification_evaluator import (
    MulticlassClassificationEvaluator,
)
from uipath.eval.models.models import (
    EvaluationResultDto,
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


def _precision(
    classes: list[str], averaging: str = "macro"
) -> ClassificationDatasetEvaluator:
    spec = PrecisionAggregatorSpec(classes=classes, averaging=averaging)  # type: ignore[arg-type]
    return ClassificationDatasetEvaluator(spec, source_evaluator="intent_match")


def _recall(
    classes: list[str], averaging: str = "macro"
) -> ClassificationDatasetEvaluator:
    spec = RecallAggregatorSpec(classes=classes, averaging=averaging)  # type: ignore[arg-type]
    return ClassificationDatasetEvaluator(spec, source_evaluator="intent_match")


def _fscore(
    classes: list[str], averaging: str = "macro", f_value: float = 1.0
) -> ClassificationDatasetEvaluator:
    spec = FScoreAggregatorSpec(
        classes=classes,
        averaging=averaging,  # type: ignore[arg-type]
        f_value=f_value,
    )
    return ClassificationDatasetEvaluator(spec, source_evaluator="intent_match")


def _details(result: object) -> ClassificationDetails:
    """Type-narrowing helper for asserting on details."""
    assert isinstance(result, NumericEvaluationResult)
    assert isinstance(result.details, ClassificationDetails)
    return result.details


def _multiclass_evaluator(
    name: str,
    classes: list[str],
    aggregators: list[BaseModel],
) -> MulticlassClassificationEvaluator:
    """Build a per-datapoint multiclass evaluator with embedded aggregators."""
    return MulticlassClassificationEvaluator.model_validate(
        {
            "id": str(uuid.uuid4()),
            "evaluatorConfig": {
                "name": name,
                "classes": classes,
                "aggregators": [spec.model_dump(by_alias=True) for spec in aggregators],
            },
        }
    )


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
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("yes", "no"),
            _result("no", "yes"),
        ]
        result = _precision(["yes", "no"], averaging="macro").evaluate(results)
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
        result = _precision(["yes", "no"], averaging="micro").evaluate(results)
        d = _details(result)
        assert d.micro == pytest.approx(0.5)
        assert result.score == pytest.approx(0.5)

    def test_three_class_macro(self) -> None:
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
        result = _precision(["cat", "dog", "bird"], averaging="macro").evaluate(
            [_result(e, a) for e, a in pairs]
        )
        d = _details(result)
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
        result = _recall(["yes", "no"], averaging="macro").evaluate(results)
        d = _details(result)
        assert d.per_class["yes"].value == pytest.approx(2 / 3)
        assert d.per_class["no"].value == pytest.approx(0.0)
        assert result.score == pytest.approx(1 / 3)

    def test_recall_differs_from_precision(self) -> None:
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("no", "yes"),
            _result("no", "yes"),
            _result("no", "no"),
        ]
        p = _details(_precision(["yes", "no"], averaging="macro").evaluate(results))
        r = _details(_recall(["yes", "no"], averaging="macro").evaluate(results))
        assert p.per_class["yes"].value == pytest.approx(0.5)
        assert p.per_class["no"].value == pytest.approx(1.0)
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
            _fscore(["yes", "no"], averaging="macro", f_value=1.0).evaluate(results)
        )
        assert f.per_class["yes"].value == pytest.approx(2 / 3)
        assert f.per_class["no"].value == pytest.approx(0.0)
        assert f.macro == pytest.approx((2 / 3 + 0.0) / 2)

    def test_f_beta_emphasizes_recall_when_beta_above_one(self) -> None:
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("no", "yes"),
            _result("no", "yes"),
            _result("no", "no"),
        ]
        f1 = _details(
            _fscore(["yes", "no"], averaging="macro", f_value=1.0).evaluate(results)
        )
        f2 = _details(
            _fscore(["yes", "no"], averaging="macro", f_value=2.0).evaluate(results)
        )
        assert f2.per_class["yes"].value > f1.per_class["yes"].value

    def test_three_class_micro_pools_across_classes(self) -> None:
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
            _fscore(["cat", "dog", "bird"], averaging="micro", f_value=1.0).evaluate(
                [_result(e, a) for e, a in pairs]
            )
        )
        assert d.micro == pytest.approx(6 / 9)


class TestSkippingAndEdgeCases:
    def test_out_of_vocab_labels_are_skipped(self) -> None:
        results = [
            _result("cat", "cat"),
            _result("cat", "platypus"),
            _result("zebra", "dog"),
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

    def test_case_insensitive(self) -> None:
        results = [_result("Cat", "CAT"), _result("DOG", "dog")]
        d = _details(_precision(["cat", "dog"]).evaluate(results))
        assert d.per_class["cat"].tp == 1
        assert d.per_class["dog"].tp == 1


class TestFactory:
    """The factory now takes an AggregatorSpec instance + source name, not a dict."""

    def test_builds_precision_from_spec(self) -> None:
        spec = PrecisionAggregatorSpec(classes=["yes", "no"], averaging="macro")
        evaluator = build_dataset_evaluator(spec, "intent_match")
        assert isinstance(evaluator, ClassificationDatasetEvaluator)
        assert evaluator.spec.type == "precision"
        assert evaluator.source_evaluator == "intent_match"
        assert evaluator.name == "intent_match.precision"

    def test_builds_recall_from_spec(self) -> None:
        spec = RecallAggregatorSpec(classes=["yes", "no"], averaging="micro")
        evaluator = build_dataset_evaluator(spec, "intent_match")
        assert isinstance(evaluator, ClassificationDatasetEvaluator)
        assert evaluator.spec.type == "recall"
        assert evaluator.name == "intent_match.recall"

    def test_builds_fscore_from_spec(self) -> None:
        spec = FScoreAggregatorSpec(
            classes=["yes", "no"], averaging="macro", f_value=2.0
        )
        evaluator = build_dataset_evaluator(spec, "intent_match")
        assert isinstance(evaluator, ClassificationDatasetEvaluator)
        assert isinstance(evaluator.spec, FScoreAggregatorSpec)
        assert evaluator.spec.f_value == 2.0


class TestAggregatorSpecJsonRoundTrip:
    """Pin the wire shape sent to the C# side."""

    def test_precision_uses_self_contained_fields(self) -> None:
        spec = PrecisionAggregatorSpec.model_validate(
            {
                "type": "precision",
                "classes": ["book", "cancel", "reschedule"],
                "averaging": "macro",
            }
        )
        dumped = spec.model_dump(by_alias=True)
        assert dumped == {
            "type": "precision",
            "classes": ["book", "cancel", "reschedule"],
            "averaging": "macro",
        }

    def test_fscore_uses_camelcase_fvalue_on_wire(self) -> None:
        spec = FScoreAggregatorSpec.model_validate(
            {
                "type": "fscore",
                "classes": ["yes", "no"],
                "averaging": "macro",
                "fValue": 1.5,
            }
        )
        assert spec.f_value == 1.5
        dumped = spec.model_dump(by_alias=True)
        assert dumped["fValue"] == 1.5
        assert "f_value" not in dumped

    def test_multiclass_evaluator_round_trips_aggregators(self) -> None:
        """Per-datapoint evaluator config carries aggregators[]; survives dump+load."""
        ev = _multiclass_evaluator(
            "intent_classifier",
            classes=["book", "cancel", "reschedule"],
            aggregators=[
                PrecisionAggregatorSpec(
                    classes=["book", "cancel", "reschedule"], averaging="macro"
                ),
                FScoreAggregatorSpec(
                    classes=["book", "cancel", "reschedule"],
                    averaging="macro",
                    f_value=1.0,
                ),
            ],
        )
        assert ev.evaluator_config.aggregators is not None
        assert len(ev.evaluator_config.aggregators) == 2
        assert ev.evaluator_config.aggregators[0].type == "precision"
        assert ev.evaluator_config.aggregators[1].type == "fscore"


class TestComputeDatasetEvaluatorResults:
    """End-to-end: runtime walks evaluator configs' aggregators[]."""

    def test_walks_aggregators_on_classification_evaluator(self) -> None:
        evaluator = _multiclass_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(classes=["yes", "no"], averaging="macro"),
                RecallAggregatorSpec(classes=["yes", "no"], averaging="macro"),
            ],
        )

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

        out = compute_dataset_evaluator_results(eval_results, [evaluator])
        # Two aggregators on intent_match → two keys, prefixed by source name.
        assert set(out) == {"intent_match.precision", "intent_match.recall"}
        precision_dto = out["intent_match.precision"]
        assert isinstance(precision_dto, EvaluationResultDto)
        assert isinstance(precision_dto.details, dict)
        # The unrelated 0.5 score from some_other_evaluator must NOT be in the matrix.
        assert precision_dto.details["n_scored"] == 2

    def test_evaluator_without_aggregators_is_skipped(self) -> None:
        evaluator = _multiclass_evaluator(
            "intent_match", classes=["yes", "no"], aggregators=[]
        )
        eval_results = [
            UiPathEvalRunResult(
                evaluation_name="dp1",
                evaluation_run_results=[
                    UiPathEvalRunResultDto(
                        evaluator_name="intent_match",
                        evaluator_id=str(uuid.uuid4()),
                        result=_result("yes", "yes"),
                    ),
                ],
            ),
        ]
        out = compute_dataset_evaluator_results(eval_results, [evaluator])
        assert out == {}

    def test_line_by_line_subresults_are_excluded(self) -> None:
        evaluator = _multiclass_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(classes=["yes", "no"], averaging="macro"),
            ],
        )
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
        out = compute_dataset_evaluator_results(eval_results, [evaluator])
        assert isinstance(out["intent_match.precision"].details, dict)
        assert out["intent_match.precision"].details["n_scored"] == 1

    def test_source_with_no_results_produces_zeroed_report(self) -> None:
        evaluator = _multiclass_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(classes=["yes", "no"], averaging="macro"),
            ],
        )
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
        out = compute_dataset_evaluator_results(eval_results, [evaluator])
        dto = out["intent_match.precision"]
        assert dto.score == 0.0
        assert isinstance(dto.details, dict)
        assert dto.details["n_scored"] == 0
