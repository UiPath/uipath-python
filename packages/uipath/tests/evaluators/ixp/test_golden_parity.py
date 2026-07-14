"""Golden parity tests for the ported IXP Measure scoring core.

Replicates ixp-platform's own test suite against the port:
  - tests/test_ixp_metrics.py (both golden-fixture paths, 29 + 28 JSONs)
  - tests/test_ranged_value.py numeric table (exact numbers)
  - typed-normalizer cases from user-model tests/test_data_type.py
  - assignment solver differential vs scipy (skipped when scipy is absent)
  - the design wiki's worked example
"""

from __future__ import annotations

import random
from decimal import Decimal
from pathlib import Path

import pytest

import uipath.eval.evaluators.ixp.ranged_value as ranged_value_module
from tests.evaluators.ixp.demo import wiki_worked_example
from tests.evaluators.ixp.ixp_utils import (
    GetIxpMetricsFromMoonTestCase,
    GetIxpMetricsTestCase,
    get_field_group_name_to_field_ids,
    get_ixp_metrics_from_moon_test_case_paths,
    get_ixp_metrics_test_case_paths,
    get_ixp_summary_metrics,
    get_raw_ixp_metrics,
    get_raw_ixp_metrics_from_moon,
)
from uipath.eval.evaluators.ixp._compat import (
    ENTITY_DEF_ID_EXTRACTION_NUMBER,
    ChoiceFieldFlag,
    Currency,
    FieldChoiceName,
    InternalCommentId,
)
from uipath.eval.evaluators.ixp.data_type_utils import (
    process_amount_field_value,
    process_bool_field_value,
    process_choice_field_value,
    process_date_field_value,
    process_monetary_field_value,
)
from uipath.eval.evaluators.ixp.extraction import (
    AmountExtraction,
    BoolExtraction,
    ChoiceExtraction,
    DateExtraction,
    MonetaryExtraction,
)
from uipath.eval.evaluators.ixp.ixp import (
    ProjectScoreQuality,
    _raw_ixp_metrics_to_summary,
)
from uipath.eval.evaluators.ixp.moon import (
    RawMoonValue,
    moon_extractions_are_equal,
)
from uipath.eval.evaluators.ixp.ranged_value import RangedValue

# --- golden fixtures, exactly as ixp-platform's test driver runs them ---


@pytest.mark.parametrize(
    "path", get_ixp_metrics_test_case_paths(), ids=lambda p: p.stem
)
def test_ixp_metrics_golden(path: Path) -> None:
    test_case = GetIxpMetricsTestCase.model_validate_json(path.read_text())
    expected = get_ixp_summary_metrics(test_case.expected)
    actual = _raw_ixp_metrics_to_summary(
        field_group_name_to_field_ids=get_field_group_name_to_field_ids(
            test_case.field_group_name_to_field_ids
        ),
        document_ids=tuple(
            InternalCommentId(document_id) for document_id in test_case.document_ids
        ),
        raw=get_raw_ixp_metrics(test_case.raw),
        field_id_to_inherits_from={},
    )
    assert actual == expected


@pytest.mark.parametrize(
    "path", get_ixp_metrics_from_moon_test_case_paths(), ids=lambda p: p.stem
)
def test_ixp_metrics_from_moon_golden(path: Path) -> None:
    test_case = GetIxpMetricsFromMoonTestCase.model_validate_json(path.read_text())
    expected = get_ixp_summary_metrics(test_case.expected)
    actual = _raw_ixp_metrics_to_summary(
        field_group_name_to_field_ids=get_field_group_name_to_field_ids(
            test_case.field_group_name_to_field_ids
        ),
        document_ids=tuple(
            InternalCommentId(document_id) for document_id in test_case.document_ids
        ),
        raw=get_raw_ixp_metrics_from_moon(test_case.raw),
        field_id_to_inherits_from={},
    )
    assert actual == expected


# --- test_ranged_value.py numeric table (verbatim expected numbers) ---

RANGED_VALUE_CASES: list[
    tuple[
        tuple[int, ...],
        tuple[int, ...],
        float,
        tuple[float, float | None],
        tuple[int, float | None],
    ]
] = [
    # (numerators, denominators, zero_division, from_mean, from_sum)
    ((), (), 0.5767, (0.5767, None), (0, None)),
    ((5,), (10,), 0.5767, (0.5, None), (5, None)),
    ((5, 7), (10, 9), 0.5767, (0.63157895, 0.07911095), (12, 1.5031081)),
    ((0, 0, 0, 0), (0, 0, 0, 0), 0.5767, (0.5767, None), (0, None)),
    ((0, 7, 0, 0), (0, 21, 0, 0), 0.5767, (0.33333333, None), (7, None)),
    (
        (0, 7, 1, 0),
        (0, 21, 10, 0),
        0.5767,
        (0.25806452, 0.049443177),
        (8, 1.5327385),
    ),
    ((0, 0, 0, 0), (15, 21, 10, 7), 0.5767, (0, 0.0), (0, 0.0)),
    ((50, 30, 20), (100, 60, 40), 1.0, (0.5, 0.0), (100, 0.0)),
    ((12, 10, 10), (80, 10, 10), 1.0, (0.32, 0.14010678), (32, 14.010678)),
    (
        (12, 42, 42),
        (100, 100, 100),
        1.0,
        (0.32, 0.031622777),
        (96, 9.486833),
    ),
    (
        (32, 42, 12),
        (20, 10, 22),
        1.0,
        (1.6538462, 0.4716814),
        (86, 24.527433),
    ),
    ((5, 0, 3, 0), (0, 0, 0, 0), 0.5767, (0.5767, None), (8, None)),
    ((5, 2, 3, 1), (0, 0, 3, 0), 0.5767, (3.6666667, None), (11, None)),
    (
        (5, 0, 3, 0),
        (6, 0, 3, 0),
        0.5767,
        (0.88888889, 0.048112522),
        (8, 0.4330127),
    ),
    (
        (5, 2, 3, 1),
        (6, 0, 3, 0),
        0.5767,
        (1.2222222, 0.057824056),
        (11, 0.5204165),
    ),
    (
        (5, 0, 3, 0) * 10,
        (6, 0, 3, 0) * 10,
        0.5767,
        (0.88888889, 0.010437072),
        (80, 0.93933644),
    ),
    (
        (5, 2, 3, 1) * 10,
        (6, 0, 3, 0) * 10,
        0.5767,
        (1.2222222, 0.010462979),
        (110, 0.94166815),
    ),
    (
        (5, 3) * 10,
        (6, 3) * 10,
        0.5767,
        (0.88888889, 0.01241184),
        (80, 1.1170656),
    ),
    (
        (5, 3) * 10 + (0, 0),
        (6, 3) * 10 + (0, 0),
        0.5767,
        (0.88888889, 0.012119592),
        (80, 1.0907632),
    ),
    (
        (5, 3) * 10 + (2, 1),
        (6, 3) * 10 + (0, 0),
        0.5767,
        (0.92222222, 0.012176689),
        (83, 1.095902),
    ),
]


@pytest.mark.parametrize(
    "numerators,denominators,zero_division,expected_mean,expected_sum",
    RANGED_VALUE_CASES,
)
def test_ranged_value(
    monkeypatch: pytest.MonkeyPatch,
    numerators: tuple[int, ...],
    denominators: tuple[int, ...],
    zero_division: float,
    expected_mean: tuple[float, float | None],
    expected_sum: tuple[int, float | None],
) -> None:
    # upstream test patches these module constants the same way
    monkeypatch.setattr(
        ranged_value_module,
        "_MINIMUM_NUM_NON_ZERO_DENOMINATORS_FOR_VARIABILITY",
        2,
    )
    monkeypatch.setattr(
        ranged_value_module, "_NUM_SIGNIFICANT_FIGURES_FOR_VARIABILITY", 8
    )
    actual_mean = RangedValue.from_mean(
        numerators=numerators,
        denominators=denominators,
        zero_division_result=zero_division,
    )
    assert actual_mean.value == pytest.approx(expected_mean[0])
    assert actual_mean.variability == expected_mean[1]

    actual_sum = RangedValue.from_sum(counts=numerators, reference_counts=denominators)
    assert actual_sum.value == pytest.approx(expected_sum[0])
    assert actual_sum.variability == expected_sum[1]


def test_ranged_value_fails_on_mismatched_lengths() -> None:
    with pytest.raises(AssertionError):
        RangedValue.from_mean(
            numerators=(1, 2, 3), denominators=(1, 2), zero_division_result=0.0
        )
    with pytest.raises(AssertionError):
        RangedValue.from_sum(counts=(1, 2, 3), reference_counts=(1, 2))


# --- typed-normalizer cases (from user-model tests/test_data_type.py) ---


def test_bool_normalizer() -> None:
    result = process_bool_field_value(" True ", None, None)
    assert result is not None
    assert result.formatted == "True"
    assert result.extraction == BoolExtraction(True)
    assert process_bool_field_value("b", None, None) is None


def test_number_normalizer() -> None:
    result = process_amount_field_value(" 123.45  ")
    assert result is not None
    assert result.formatted == "123.45"
    assert result.extraction == AmountExtraction(Decimal("123.45"))
    assert process_amount_field_value("a b a a ") is None
    # thousands separators strip; parsed values compare equal
    one_thousand = process_amount_field_value("1,000.00")
    plain = process_amount_field_value("1000")
    assert one_thousand is not None and plain is not None
    assert one_thousand.extraction == plain.extraction


def test_money_normalizer() -> None:
    result = process_monetary_field_value(" -1131.11121 USD  ")
    assert result is not None
    assert result.extraction == MonetaryExtraction(
        currency=Currency.USD,
        amount=AmountExtraction(Decimal("-1131.11121")),
    )
    amount_only = process_monetary_field_value(" 123.45  ")
    assert amount_only is not None
    assert amount_only.extraction == MonetaryExtraction(
        currency=None, amount=AmountExtraction(Decimal("123.45"))
    )
    assert process_monetary_field_value(" aBcD  ") is None


def test_date_normalizer() -> None:
    result = process_date_field_value("2023-12-12 ", None, None)
    assert result is not None
    assert result.formatted == "2023-12-12T00:00:00Z"
    assert result.extraction == DateExtraction(
        year=2023,
        month=12,
        day=12,
        hours=None,
        minutes=None,
        seconds=None,
        nanoseconds=None,
        iana_timezone=None,
    )
    assert process_date_field_value("a", None, None) is None


def test_choice_normalizer_out_of_domain_quirk() -> None:
    # parity checklist §4.5: without ALLOW_OUT_OF_DOMAIN two DIFFERENT
    # unmatched values both normalize to name=None → equal
    no_flags: frozenset[ChoiceFieldFlag] = frozenset()
    first = process_choice_field_value("apple", (), no_flags)
    second = process_choice_field_value("banana", (), no_flags)
    assert first is not None and second is not None
    assert first.extraction == ChoiceExtraction(name=None)
    assert first.extraction == second.extraction
    # with ALLOW_OUT_OF_DOMAIN the raw name is kept → not equal
    allow = frozenset({ChoiceFieldFlag.ALLOW_OUT_OF_DOMAIN})
    kept = process_choice_field_value("apple", (), allow)
    assert kept is not None
    assert kept.extraction == ChoiceExtraction(name=FieldChoiceName("apple"))


def test_typed_equality_rules() -> None:
    def value(raw: str) -> RawMoonValue:
        return RawMoonValue(raw)

    number = (ENTITY_DEF_ID_EXTRACTION_NUMBER,)
    # parsed == parsed even though raw differs
    assert moon_extractions_are_equal(value("1,000.00"), value("1000"), number)
    # raw == raw still wins when parsing fails on both sides
    assert moon_extractions_are_equal(value("n/a"), value("n/a"), number)
    assert not moon_extractions_are_equal(value("n/a"), value("none"), number)
    # plain text is exact match only
    assert moon_extractions_are_equal(value("a"), value("a"), ())
    assert not moon_extractions_are_equal(value("a"), value("A"), ())
    assert moon_extractions_are_equal(None, None, ())
    assert not moon_extractions_are_equal(value("a"), None, ())


# --- assignment solver differential vs scipy ---


def test_assignment_matches_scipy_exactly() -> None:
    np = pytest.importorskip("numpy")
    scipy_optimize = pytest.importorskip("scipy.optimize")

    from uipath.eval.evaluators.ixp.assignment import linear_sum_assignment

    rng = random.Random(20260713)
    for _ in range(2000):
        num_rows = rng.randint(1, 8)
        num_cols = rng.randint(1, 8)
        matrix = [
            [float(rng.randint(0, 3)) for _ in range(num_cols)] for _ in range(num_rows)
        ]
        scipy_rows, scipy_cols = scipy_optimize.linear_sum_assignment(
            np.array(matrix, dtype=np.float32), maximize=True
        )
        our_rows, our_cols = linear_sum_assignment(matrix, maximize=True)
        assert list(scipy_rows) == our_rows
        assert list(scipy_cols) == our_cols


# --- the design wiki's worked example ---


def test_wiki_worked_example() -> None:
    summary = wiki_worked_example()
    group = next(iter(summary.ixp_metrics.field_groups_metrics.values()))
    field_f1s = [
        metrics.f1_score.value
        for group_fields in summary.ixp_metrics.fields_metrics.values()
        for metrics in group_fields.values()
    ]
    # the wiki's documented numbers: TP=5 FP=1 FN=3
    assert group.precision.value == pytest.approx(5 / 6)
    assert group.recall.value == pytest.approx(5 / 8)
    assert group.f1_score.value == pytest.approx(5 / 7)
    assert sorted(field_f1s) == pytest.approx([0.5, 0.8, 0.8])
    assert summary.project_score == pytest.approx(0.70)
    assert summary.project_indicators.project_score_quality is ProjectScoreQuality.GOOD
