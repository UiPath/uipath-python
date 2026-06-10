"""Tests for the precision / recall / fscore aggregator functions."""

from __future__ import annotations

import math

import pytest

from uipath.eval.aggregators import (
    AggregatorConfig,
    FScoreAggregator,
    Observation,
    PrecisionAggregator,
    RecallAggregator,
    get_function,
)
from uipath.eval.aggregators._counts import (
    class_counts,
    resolve_classes,
)


def obs(expected: str | None, actual: str | None) -> Observation:
    return Observation(expected=expected, actual=actual)


# ---------------------------------------------------------------------------
# Class resolution + counting (shared core)
# ---------------------------------------------------------------------------


class TestClassResolution:
    def test_explicit_classes_take_precedence(self) -> None:
        observed = [obs("a", "a")]
        assert resolve_classes(["x", "y"], observed) == ["x", "y"]

    def test_inferred_in_order_of_first_appearance(self) -> None:
        observed = [obs("b", "b"), obs("a", "a"), obs("b", "b"), obs("c", None)]
        assert resolve_classes(None, observed) == ["b", "a", "c"]

    def test_inferred_ignores_none_expected(self) -> None:
        observed = [obs(None, "x"), obs("a", "a")]
        assert resolve_classes(None, observed) == ["a"]


class TestClassCounts:
    def test_per_class_tp_fp_fn(self) -> None:
        # 6 rows, all expected=book. agent: 2x book, 4x cancel.
        observed = [obs("book", "book"), obs("book", "book")] + [
            obs("book", "cancel") for _ in range(4)
        ]
        counts = class_counts(["book", "cancel"], observed)
        assert counts["book"].tp == 2
        assert counts["book"].fp == 0
        assert counts["book"].fn == 4
        assert counts["book"].support == 6
        # cancel: never the expected, only the predicted (wrongly)
        assert counts["cancel"].tp == 0
        assert counts["cancel"].fp == 4
        assert counts["cancel"].fn == 0
        assert counts["cancel"].support == 0

    def test_skips_none_expected_or_actual(self) -> None:
        observed = [obs(None, "a"), obs("a", None), obs("a", "a")]
        counts = class_counts(["a"], observed)
        assert counts["a"].tp == 1 and counts["a"].fp == 0 and counts["a"].fn == 0


# ---------------------------------------------------------------------------
# Precision
# ---------------------------------------------------------------------------


class TestPrecision:
    def _cfg(self, **kwargs) -> AggregatorConfig:
        return AggregatorConfig(function="precision", **kwargs)

    def test_perfect_multi_class_macro(self) -> None:
        observed = [obs("a", "a"), obs("b", "b"), obs("c", "c")]
        assert (
            PrecisionAggregator().compute(self._cfg(classes=["a", "b", "c"]), observed)
            == 1.0
        )

    def test_hca_style_macro(self) -> None:
        # All expected=book; agent gets 2 right, 4 wrong (as cancel)
        observed = [obs("book", "book"), obs("book", "book")] + [
            obs("book", "cancel") for _ in range(4)
        ]
        # book: precision = 2/(2+0) = 1.0
        # cancel: precision = 0/(0+4) = 0.0
        # macro = (1.0 + 0.0)/2 = 0.5
        out = PrecisionAggregator().compute(
            self._cfg(classes=["book", "cancel"]), observed
        )
        assert math.isclose(out, 0.5, abs_tol=1e-9)

    def test_micro_pools_tp_fp(self) -> None:
        observed = [obs("book", "book"), obs("book", "book")] + [
            obs("book", "cancel") for _ in range(4)
        ]
        # micro = tp/(tp+fp) = 2/(2+4) = 1/3
        out = PrecisionAggregator().compute(
            self._cfg(classes=["book", "cancel"], average="micro"), observed
        )
        assert math.isclose(out, 1 / 3, abs_tol=1e-9)

    def test_binary_positive_class(self) -> None:
        # 4 spam expected, agent calls 3 spam (2 tp + 1 fp on a "ham" doc)
        observed = (
            [obs("spam", "spam")] * 2
            + [obs("spam", "ham")] * 2
            + [obs("ham", "spam")] * 1
            + [obs("ham", "ham")] * 1
        )
        out = PrecisionAggregator().compute(
            AggregatorConfig(function="precision", positive_class="spam"), observed
        )
        assert math.isclose(out, 2 / 3, abs_tol=1e-9)  # 2 TP / (2 TP + 1 FP)

    def test_auto_inferred_classes(self) -> None:
        observed = [obs("a", "a"), obs("b", "b")]
        out = PrecisionAggregator().compute(self._cfg(), observed)  # no classes given
        assert out == 1.0

    def test_empty_observations_returns_zero(self) -> None:
        assert PrecisionAggregator().compute(self._cfg(classes=["a"]), []) == 0.0


# ---------------------------------------------------------------------------
# Recall
# ---------------------------------------------------------------------------


class TestRecall:
    def _cfg(self, **kwargs) -> AggregatorConfig:
        return AggregatorConfig(function="recall", **kwargs)

    def test_hca_style_macro(self) -> None:
        observed = [obs("book", "book"), obs("book", "book")] + [
            obs("book", "cancel") for _ in range(4)
        ]
        # book: recall = 2/(2+4) = 1/3
        # cancel: recall = 0/(0+0) = 0
        # macro = (1/3 + 0)/2 = 1/6
        out = RecallAggregator().compute(
            self._cfg(classes=["book", "cancel"]), observed
        )
        assert math.isclose(out, 1 / 6, abs_tol=1e-9)

    def test_micro(self) -> None:
        observed = [obs("book", "book"), obs("book", "book")] + [
            obs("book", "cancel") for _ in range(4)
        ]
        # micro = tp/(tp+fn) = 2/(2+4) = 1/3
        out = RecallAggregator().compute(
            self._cfg(classes=["book", "cancel"], average="micro"), observed
        )
        assert math.isclose(out, 1 / 3, abs_tol=1e-9)

    def test_perfect_three_class(self) -> None:
        observed = [obs("a", "a"), obs("b", "b"), obs("c", "c")]
        assert RecallAggregator().compute(self._cfg(classes=["a", "b", "c"]), observed) == 1.0


# ---------------------------------------------------------------------------
# F-score
# ---------------------------------------------------------------------------


class TestFScore:
    def _cfg(self, **kwargs) -> AggregatorConfig:
        return AggregatorConfig(function="fscore", **kwargs)

    def test_f1_perfect(self) -> None:
        observed = [obs("a", "a"), obs("b", "b")]
        assert FScoreAggregator().compute(self._cfg(classes=["a", "b"]), observed) == 1.0

    def test_f1_hca(self) -> None:
        observed = [obs("book", "book"), obs("book", "book")] + [
            obs("book", "cancel") for _ in range(4)
        ]
        # book: P=1, R=1/3 → F1 = 2 * 1 * (1/3) / (1 + 1/3) = (2/3) / (4/3) = 0.5
        # cancel: P=0, R=0 → F1 = 0
        # macro = 0.25
        out = FScoreAggregator().compute(self._cfg(classes=["book", "cancel"]), observed)
        assert math.isclose(out, 0.25, abs_tol=1e-9)

    def test_f2_weights_recall_more(self) -> None:
        observed = [obs("book", "book"), obs("book", "book")] + [
            obs("book", "cancel") for _ in range(4)
        ]
        # F2 for book: (1+4) * P * R / (4P + R) = 5 * 1 * (1/3) / (4 + 1/3)
        # = (5/3) / (13/3) = 5/13 ≈ 0.3846
        # macro = 0.3846 / 2 ≈ 0.1923
        out = FScoreAggregator().compute(
            self._cfg(classes=["book", "cancel"], beta=2.0), observed
        )
        assert math.isclose(out, (5 / 13) / 2, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_built_ins_resolve(self) -> None:
        assert get_function("precision").name == "precision"
        assert get_function("recall").name == "recall"
        assert get_function("fscore").name == "fscore"

    def test_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown aggregator function"):
            get_function("histogram")


# ---------------------------------------------------------------------------
# AggregatorConfig.output_key
# ---------------------------------------------------------------------------


class TestOutputKey:
    def test_simple(self) -> None:
        assert AggregatorConfig(function="precision").output_key() == "precision"

    def test_fscore_beta_qualifier(self) -> None:
        assert (
            AggregatorConfig(function="fscore", beta=2.0).output_key() == "fscore@beta=2.0"
        )
        # beta=1.0 stays unqualified
        assert AggregatorConfig(function="fscore", beta=1.0).output_key() == "fscore"

    def test_average_qualifier(self) -> None:
        assert (
            AggregatorConfig(function="precision", average="micro").output_key()
            == "precision@average=micro"
        )

    def test_multiple_qualifiers(self) -> None:
        cfg = AggregatorConfig(function="fscore", beta=2.0, average="weighted")
        assert cfg.output_key() == "fscore@beta=2.0,average=weighted"
