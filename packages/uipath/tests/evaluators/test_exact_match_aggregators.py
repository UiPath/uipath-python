"""ExactMatch aggregator config surface.

The platform's dataset-evaluator pass (Agents repo) reads ``classes`` and
``aggregators`` off the ExactMatch evaluator config. These tests pin the SDK
side of that wire contract: the discriminated spec union, the config fields,
and the config validator. The aggregation math lives in
``classification_dataset_evaluators.py`` (tested separately) and is consumed
by both `uipath eval` and the platform's python-dataset-eval-worker.
"""

import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from uipath.eval.evaluators._aggregator_specs import (
    AggregatorSpec,
    ConfusionMatrixAggregatorSpec,
    FScoreAggregatorSpec,
    PrecisionAggregatorSpec,
    RecallAggregatorSpec,
)
from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator


def _evaluator(config: dict) -> ExactMatchEvaluator:
    return ExactMatchEvaluator.model_validate(
        {"evaluatorConfig": config, "id": str(uuid.uuid4())}
    )


class TestAggregatorSpecUnion:
    """Wire shape sent to the platform — {type, averaging, [fValue]}."""

    def test_discriminates_on_type(self) -> None:
        adapter = TypeAdapter(AggregatorSpec)
        assert isinstance(
            adapter.validate_python({"type": "precision", "averaging": "macro"}),
            PrecisionAggregatorSpec,
        )
        assert isinstance(
            adapter.validate_python({"type": "recall", "averaging": "micro"}),
            RecallAggregatorSpec,
        )
        fscore = adapter.validate_python(
            {"type": "fscore", "averaging": "macro", "fValue": 2.0}
        )
        assert isinstance(fscore, FScoreAggregatorSpec)
        assert fscore.f_value == 2.0
        assert isinstance(
            adapter.validate_python({"type": "confusion_matrix"}),
            ConfusionMatrixAggregatorSpec,
        )

    def test_specs_do_not_carry_classes(self) -> None:
        # Classes live once on the evaluator config, shared by all aggregators.
        dumped = PrecisionAggregatorSpec(averaging="macro").model_dump(by_alias=True)
        assert dumped == {"type": "precision", "averaging": "macro"}

    def test_fscore_uses_camelcase_fvalue_on_wire(self) -> None:
        dumped = FScoreAggregatorSpec(averaging="macro", f_value=1.5).model_dump(
            by_alias=True
        )
        assert dumped["fValue"] == 1.5
        assert "f_value" not in dumped

    def test_fscore_fvalue_is_bounded(self) -> None:
        # A huge beta overflows beta² to inf → NaN score → unrepresentable JSON.
        adapter = TypeAdapter(AggregatorSpec)
        for bad in (0, -1, 1e200, float("inf"), float("nan")):
            with pytest.raises(ValidationError):
                adapter.validate_python(
                    {"type": "fscore", "averaging": "macro", "fValue": bad}
                )


class TestExactMatchAggregatorConfig:
    def test_accepts_aggregators_with_classes(self) -> None:
        ev = _evaluator(
            {
                "name": "IntentClassifier",
                "classes": ["book", "cancel", "reschedule"],
                "aggregators": [
                    {"type": "precision", "averaging": "macro"},
                    {"type": "recall", "averaging": "macro"},
                    {"type": "fscore", "averaging": "macro", "fValue": 1.0},
                ],
            }
        )
        config = ev.evaluator_config
        assert config.classes == ["book", "cancel", "reschedule"]
        assert config.aggregators is not None
        assert [s.type for s in config.aggregators] == ["precision", "recall", "fscore"]

    def test_rejects_aggregators_without_classes(self) -> None:
        # The SDK wraps pydantic's ValidationError in UiPathEvaluationError at
        # evaluator construction; match the message rather than the type.
        with pytest.raises(Exception, match="classes"):
            _evaluator(
                {
                    "name": "IntentClassifier",
                    "aggregators": [{"type": "precision", "averaging": "macro"}],
                }
            )

    def test_rejects_case_duplicate_classes(self) -> None:
        # Labels match case-insensitively, so "Yes"/"yes" would collapse onto
        # one matrix index and silently skew every metric.
        with pytest.raises(Exception, match="unique"):
            _evaluator(
                {
                    "name": "IntentClassifier",
                    "classes": ["Yes", "yes"],
                    "aggregators": [{"type": "precision", "averaging": "macro"}],
                }
            )

    def test_rejects_blank_class_labels(self) -> None:
        with pytest.raises(Exception, match="non-blank"):
            _evaluator(
                {
                    "name": "IntentClassifier",
                    "classes": ["yes", "  "],
                    "aggregators": [{"type": "precision", "averaging": "macro"}],
                }
            )

    def test_rejects_aggregators_with_line_by_line(self) -> None:
        # Per-line results carry no expected/actual labels — every datapoint
        # would land in n_skipped and all metrics would silently read 0.
        with pytest.raises(Exception, match="line_by_line"):
            _evaluator(
                {
                    "name": "IntentClassifier",
                    "classes": ["yes", "no"],
                    "lineByLineEvaluator": True,
                    "aggregators": [{"type": "precision", "averaging": "macro"}],
                }
            )

    def test_plain_config_needs_neither_field(self) -> None:
        ev = _evaluator({"name": "PlainMatch"})
        assert ev.evaluator_config.classes is None
        assert ev.evaluator_config.aggregators is None

    def test_round_trips_through_dump_and_load(self) -> None:
        config = {
            "name": "IntentClassifier",
            "classes": ["yes", "no"],
            "aggregators": [{"type": "fscore", "averaging": "micro", "fValue": 2.0}],
        }
        ev = _evaluator(config)
        dumped = ev.evaluator_config.model_dump(by_alias=True, exclude_none=True)
        assert dumped["classes"] == ["yes", "no"]
        assert dumped["aggregators"] == [
            {"type": "fscore", "averaging": "micro", "fValue": 2.0}
        ]
