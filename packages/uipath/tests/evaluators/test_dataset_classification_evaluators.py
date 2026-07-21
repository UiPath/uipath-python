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
    ConfusionMatrixAggregatorSpec,
    FScoreAggregatorSpec,
    PrecisionAggregatorSpec,
    RecallAggregatorSpec,
)
from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification
from uipath.eval.evaluators.classification_dataset_evaluators import (
    AveragedMetrics,
    ClassificationDatasetEvaluator,
    ClassificationDetails,
    PerClassMetrics,
)
from uipath.eval.evaluators.dataset_evaluator_factory import build_dataset_evaluator
from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator
from uipath.eval.models.models import (
    EvaluationResultDto,
    NumericEvaluationResult,
)
from uipath.eval.runtime._types import (
    UiPathEvalRunResult,
    UiPathEvalRunResultDto,
)
from uipath.eval.runtime.runtime import compute_dataset_evaluator_results


def _result(expected: str, actual: str) -> EvaluationResultDto:
    """Build an EvaluationResultDto carrying an expected/actual justification."""
    justification = BaseEvaluatorJustification(expected=expected, actual=actual)
    return EvaluationResultDto(
        score=1.0 if expected.lower() == actual.lower() else 0.0,
        details=justification.model_dump(),
    )


def _precision(
    classes: list[str], averaging: str = "macro"
) -> ClassificationDatasetEvaluator:
    spec = PrecisionAggregatorSpec(averaging=averaging)  # type: ignore[arg-type]
    return ClassificationDatasetEvaluator(
        spec, source_evaluator="intent_match", classes=classes
    )


def _recall(
    classes: list[str], averaging: str = "macro"
) -> ClassificationDatasetEvaluator:
    spec = RecallAggregatorSpec(averaging=averaging)  # type: ignore[arg-type]
    return ClassificationDatasetEvaluator(
        spec, source_evaluator="intent_match", classes=classes
    )


def _fscore(
    classes: list[str], averaging: str = "macro", f_value: float = 1.0
) -> ClassificationDatasetEvaluator:
    spec = FScoreAggregatorSpec(
        averaging=averaging,  # type: ignore[arg-type]
        f_value=f_value,
    )
    return ClassificationDatasetEvaluator(
        spec, source_evaluator="intent_match", classes=classes
    )


def _details(result: object) -> ClassificationDetails:
    """Type-narrowing helper for asserting on details."""
    assert isinstance(result, NumericEvaluationResult)
    assert isinstance(result.details, ClassificationDetails)
    return result.details


# per_class / macro / micro are Optional on ClassificationDetails (the
# confusion_matrix variant omits them). Scalar-metric tests always populate
# them; these accessors assert-narrow to the non-Optional type so mypy is happy.
def _pc(d: ClassificationDetails) -> dict[str, PerClassMetrics]:
    assert d.per_class is not None
    return d.per_class


def _macro(d: ClassificationDetails) -> AveragedMetrics:
    assert d.macro is not None
    return d.macro


def _micro(d: ClassificationDetails) -> AveragedMetrics:
    assert d.micro is not None
    return d.micro


def _exact_match_evaluator(
    name: str,
    classes: list[str],
    aggregators: list[BaseModel],
) -> ExactMatchEvaluator:
    """Build a per-datapoint ExactMatch evaluator with attached aggregators.

    Aggregators + classes live on the evaluator config — every aggregator on
    the same ExactMatch config shares the ``classes`` vocabulary declared here.
    """
    return ExactMatchEvaluator.model_validate(
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
        assert _pc(d)["cat"].tp == 0
        assert _pc(d)["cat"].tn == 0

    def test_confusion_matrix_is_predicted_by_expected(self) -> None:
        # Pin the documented orientation: confusion_matrix[predicted][expected].
        # Differs from sklearn's [true][predicted] convention.
        results = [
            _result("cat", "cat"),  # expected=cat, predicted=cat -> [cat][cat]
            _result("cat", "dog"),  # expected=cat, predicted=dog -> [dog][cat]
            _result("dog", "dog"),  # expected=dog, predicted=dog -> [dog][dog]
            _result("dog", "dog"),
        ]
        d = _details(_precision(["cat", "dog"]).evaluate(results))
        # classes -> index: cat=0, dog=1
        # [predicted=cat][expected=cat] = 1
        assert d.confusion_matrix[0][0] == 1
        # [predicted=dog][expected=cat] = 1 (the FP for dog / FN for cat)
        assert d.confusion_matrix[1][0] == 1
        # [predicted=dog][expected=dog] = 2
        assert d.confusion_matrix[1][1] == 2
        # [predicted=cat][expected=dog] = 0
        assert d.confusion_matrix[0][1] == 0

    def test_precision_two_class_macro(self) -> None:
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
        assert _pc(d)["yes"].precision == pytest.approx(2 / 3)
        assert _pc(d)["no"].precision == pytest.approx(0.0)
        assert _macro(d).precision == pytest.approx((2 / 3 + 0.0) / 2)
        assert result.score == pytest.approx(_macro(d).precision)

    def test_two_class_micro_equals_accuracy(self) -> None:
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("yes", "no"),
            _result("no", "yes"),
        ]
        result = _precision(["yes", "no"], averaging="micro").evaluate(results)
        d = _details(result)
        assert _micro(d).precision == pytest.approx(0.5)
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
            m = _pc(d)[label]
            assert m.tp == 2 and m.fp == 1 and m.fn == 1 and m.tn == 5
            assert m.precision == pytest.approx(2 / 3)
        assert _macro(d).precision == pytest.approx(2 / 3)
        assert result.score == pytest.approx(2 / 3)


class TestRecallEvaluator:
    def test_recall_two_class_macro(self) -> None:
        results = [
            _result("yes", "yes"),
            _result("yes", "yes"),
            _result("yes", "no"),
            _result("no", "yes"),
        ]
        result = _recall(["yes", "no"], averaging="macro").evaluate(results)
        d = _details(result)
        assert _pc(d)["yes"].recall == pytest.approx(2 / 3)
        assert _pc(d)["no"].recall == pytest.approx(0.0)
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
        assert _pc(p)["yes"].precision == pytest.approx(0.5)
        assert _pc(p)["no"].precision == pytest.approx(1.0)
        assert _pc(r)["yes"].recall == pytest.approx(1.0)
        assert _pc(r)["no"].recall == pytest.approx(1 / 3)


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
        assert _pc(f)["yes"].f_score == pytest.approx(2 / 3)
        assert _pc(f)["no"].f_score == pytest.approx(0.0)
        assert _macro(f).f_score == pytest.approx((2 / 3 + 0.0) / 2)

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
        assert _pc(f2)["yes"].f_score > _pc(f1)["yes"].f_score

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
        assert _micro(d).f_score == pytest.approx(6 / 9)


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
        assert _pc(d)["cat"].tp == 1
        assert _pc(d)["dog"].tp == 1


class TestFactory:
    """The factory builds from an AggregatorSpec instance + source name."""

    def test_builds_precision_from_spec(self) -> None:
        spec = PrecisionAggregatorSpec(averaging="macro")
        evaluator = build_dataset_evaluator(spec, "intent_match", classes=["yes", "no"])
        assert isinstance(evaluator, ClassificationDatasetEvaluator)
        assert evaluator.spec.type == "precision"
        assert evaluator.source_evaluator == "intent_match"

    def test_builds_recall_from_spec(self) -> None:
        spec = RecallAggregatorSpec(averaging="micro")
        evaluator = build_dataset_evaluator(spec, "intent_match", classes=["yes", "no"])
        assert isinstance(evaluator, ClassificationDatasetEvaluator)
        assert evaluator.spec.type == "recall"

    def test_builds_fscore_from_spec(self) -> None:
        spec = FScoreAggregatorSpec(averaging="macro", f_value=2.0)
        evaluator = build_dataset_evaluator(spec, "intent_match", classes=["yes", "no"])
        assert isinstance(evaluator, ClassificationDatasetEvaluator)
        assert isinstance(evaluator.spec, FScoreAggregatorSpec)
        assert evaluator.spec.f_value == 2.0


class TestAggregatorSpecJsonRoundTrip:
    """Pin the wire shape sent to the C# side."""

    def test_precision_spec_wire_shape(self) -> None:
        """Specs carry only metric-shape fields; ``classes`` lives on the
        parent evaluator config.
        """
        spec = PrecisionAggregatorSpec.model_validate(
            {
                "type": "precision",
                "averaging": "macro",
            }
        )
        dumped = spec.model_dump(by_alias=True)
        assert dumped == {
            "type": "precision",
            "averaging": "macro",
        }

    def test_fscore_uses_camelcase_fvalue_on_wire(self) -> None:
        spec = FScoreAggregatorSpec.model_validate(
            {
                "type": "fscore",
                "averaging": "macro",
                "fValue": 1.5,
            }
        )
        assert spec.f_value == 1.5
        dumped = spec.model_dump(by_alias=True)
        assert dumped["fValue"] == 1.5
        assert "f_value" not in dumped

    def test_exact_match_evaluator_round_trips_aggregators(self) -> None:
        """Per-datapoint evaluator config carries aggregators[]; survives dump+load."""
        ev = _exact_match_evaluator(
            "intent_classifier",
            classes=["book", "cancel", "reschedule"],
            aggregators=[
                PrecisionAggregatorSpec(averaging="macro"),
                FScoreAggregatorSpec(averaging="macro", f_value=1.0),
            ],
        )
        assert ev.evaluator_config.aggregators is not None
        assert len(ev.evaluator_config.aggregators) == 2
        assert ev.evaluator_config.aggregators[0].type == "precision"
        assert ev.evaluator_config.aggregators[1].type == "fscore"


class TestComputeDatasetEvaluatorResults:
    """End-to-end: runtime walks evaluator configs' aggregators[]."""

    def test_walks_aggregators_on_classification_evaluator(self) -> None:
        evaluator = _exact_match_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(averaging="macro"),
                RecallAggregatorSpec(averaging="macro"),
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
        assert set(out) == {"intent_match::precision", "intent_match::recall"}
        precision_dto = out["intent_match::precision"]
        assert isinstance(precision_dto, EvaluationResultDto)
        assert isinstance(precision_dto.details, dict)
        # The unrelated 0.5 score from some_other_evaluator must NOT be in the matrix.
        assert precision_dto.details["nScored"] == 2

    def test_evaluator_without_aggregators_is_skipped(self) -> None:
        evaluator = _exact_match_evaluator(
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
        evaluator = _exact_match_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(averaging="macro"),
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
        assert isinstance(out["intent_match::precision"].details, dict)
        assert out["intent_match::precision"].details["nScored"] == 1

    def test_source_with_no_results_produces_zeroed_report(self) -> None:
        evaluator = _exact_match_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(averaging="macro"),
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
        dto = out["intent_match::precision"]
        assert dto.score == 0.0
        assert isinstance(dto.details, dict)
        assert dto.details["nScored"] == 0

    def test_duplicate_datapoint_results_are_deduped(self) -> None:
        """A datapoint with two DTOs for one evaluator (e.g. a real result plus
        a details-less zero from the partial-failure path, or a retry/resume
        re-feed) must count once — no inflated nTotal/nSkipped, no double-count
        in the matrix. The parseable DTO wins over the details-less one."""
        evaluator = _exact_match_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[PrecisionAggregatorSpec(averaging="macro")],
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
                    # Duplicate: details-less zero (partial-failure path shape).
                    UiPathEvalRunResultDto(
                        evaluator_name="intent_match",
                        evaluator_id=str(uuid.uuid4()),
                        result=EvaluationResultDto(score=0.0),
                    ),
                ],
            ),
        ]
        out = compute_dataset_evaluator_results(eval_results, [evaluator])
        details = out["intent_match::precision"].details
        assert isinstance(details, dict)
        # One datapoint in, one counted — not two, and the parseable one scored.
        assert details["nTotal"] == 1
        assert details["nScored"] == 1
        assert details["nSkipped"] == 0

    def test_duplicate_aggregator_type_disambiguates_by_averaging(self) -> None:
        """Two aggregators of the same type get distinct keys (no overwrite)."""
        evaluator = _exact_match_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(averaging="macro"),
                PrecisionAggregatorSpec(averaging="micro"),
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
                ],
            ),
        ]
        out = compute_dataset_evaluator_results(eval_results, [evaluator])
        # Same type appears twice → averaging suffix disambiguates so neither
        # is silently overwritten.
        assert set(out) == {
            "intent_match::precision.macro",
            "intent_match::precision.micro",
        }

    def test_exact_duplicate_specs_are_deduped(self) -> None:
        """Identical specs collapse to one result; duplicate confusion_matrix
        (no averaging field) must not crash key disambiguation."""
        evaluator = _exact_match_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[
                PrecisionAggregatorSpec(averaging="macro"),
                PrecisionAggregatorSpec(averaging="macro"),
                ConfusionMatrixAggregatorSpec(),
                ConfusionMatrixAggregatorSpec(),
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
                ],
            ),
        ]
        out = compute_dataset_evaluator_results(eval_results, [evaluator])
        assert set(out) == {
            "intent_match::precision",
            "intent_match::confusion_matrix",
        }

    def test_details_are_dumped_to_camelcase_wire_shape(self) -> None:
        """The local path ships the same JSON shape as the platform worker:
        camelCase keys, absent (not null) optional fields."""
        evaluator = _exact_match_evaluator(
            "intent_match",
            classes=["yes", "no"],
            aggregators=[ConfusionMatrixAggregatorSpec()],
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
        details = out["intent_match::confusion_matrix"].details
        assert isinstance(details, dict)
        assert details["confusionMatrix"] == [[1, 0], [0, 0]]
        assert details["nScored"] == 1
        # confusion_matrix variant: scalar fields are absent, not null.
        assert "perClass" not in details and "macro" not in details
