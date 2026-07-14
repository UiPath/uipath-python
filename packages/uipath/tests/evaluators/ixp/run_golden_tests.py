"""Golden parity tests for the ported IXP Measure scoring core.

Replicates ixp-platform's own test suite against the port:
  1. tests/test_ixp_metrics.py::test_ixp_metrics           (57 golden JSONs)
  2. tests/test_ixp_metrics.py::test_ixp_metrics_from_moon (28 golden JSONs)
  3. tests/test_ranged_value.py numeric table              (exact numbers)
  4. Typed-normalizer cases from user-model tests/test_data_type.py
  5. Assignment solver differential vs scipy (skipped if scipy missing)

Run:
    cd packages/uipath/tests/evaluators/ixp
    uv run --no-project --python 3.12 --with pydantic --with python-dateutil \
        --with scipy python run_golden_tests.py
"""

from __future__ import annotations

import math
import sys
import traceback
from dataclasses import fields, is_dataclass
from decimal import Decimal

from ixp_utils import (  # noqa: E402 (does the sys.path setup for `ixp`)
    GetIxpMetricsFromMoonTestCase,
    GetIxpMetricsTestCase,
    get_field_group_name_to_field_ids,
    get_ixp_metrics_from_moon_test_case_paths,
    get_ixp_metrics_test_case_paths,
    get_ixp_summary_metrics,
    get_raw_ixp_metrics,
    get_raw_ixp_metrics_from_moon,
)

from ixp import ranged_value as ranged_value_module
from ixp._compat import (
    ENTITY_DEF_ID_EXTRACTION_NUMBER,
    ChoiceFieldFlag,
    Currency,
    InternalCommentId,
)
from ixp.data_type_utils import (
    process_amount_field_value,
    process_bool_field_value,
    process_choice_field_value,
    process_date_field_value,
    process_monetary_field_value,
)
from ixp.extraction import (
    AmountExtraction,
    BoolExtraction,
    ChoiceExtraction,
    DateExtraction,
    MonetaryExtraction,
)
from ixp.ixp import _raw_ixp_metrics_to_summary
from ixp.moon import moon_extractions_are_equal
from ixp.ranged_value import RangedValue

PASSED = 0
FAILED = 0
FAILURES: list[str] = []


def check(name: str, fn) -> None:
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
    except Exception:
        FAILED += 1
        FAILURES.append(f"{name}\n{traceback.format_exc()}")
        print(f"  FAIL {name}")


def _diff_dataclass(actual, expected, path="") -> list[str]:
    """Field-level diff so a golden mismatch names the exact metric."""
    diffs: list[str] = []
    if is_dataclass(actual) and is_dataclass(expected):
        for f in fields(actual):
            diffs.extend(
                _diff_dataclass(
                    getattr(actual, f.name),
                    getattr(expected, f.name),
                    f"{path}.{f.name}",
                )
            )
    elif isinstance(actual, dict) or hasattr(actual, "items"):
        for key in set(list(actual.keys()) + list(expected.keys())):
            diffs.extend(
                _diff_dataclass(
                    actual.get(key), expected.get(key), f"{path}[{key!r}]"
                )
            )
    elif isinstance(actual, tuple) and isinstance(expected, tuple):
        if len(actual) != len(expected):
            diffs.append(f"{path}: len {len(actual)} != {len(expected)}")
        else:
            for i, (a, e) in enumerate(zip(actual, expected)):
                diffs.extend(_diff_dataclass(a, e, f"{path}[{i}]"))
    elif actual != expected:
        diffs.append(f"{path}: actual={actual!r} expected={expected!r}")
    return diffs


# --- 1 + 2: the golden fixtures, exactly as ixp-platform's test driver ---


def run_golden_ixp_metrics() -> None:
    print(f"[1] golden ixp_metrics fixtures")
    for path in get_ixp_metrics_test_case_paths():

        def run(path=path):
            test_case = GetIxpMetricsTestCase.parse_file(path)
            expected = get_ixp_summary_metrics(test_case.expected)
            actual = _raw_ixp_metrics_to_summary(
                field_group_name_to_field_ids=get_field_group_name_to_field_ids(
                    test_case.field_group_name_to_field_ids
                ),
                document_ids=tuple(
                    InternalCommentId(document_id)
                    for document_id in test_case.document_ids
                ),
                raw=get_raw_ixp_metrics(test_case.raw),
                field_id_to_inherits_from={},
            )
            if actual != expected:
                diffs = _diff_dataclass(actual, expected)
                raise AssertionError(
                    f"{path.name}:\n  " + "\n  ".join(diffs[:20])
                )

        check(path.name, run)


def run_golden_from_moon() -> None:
    print(f"[2] golden from_moon fixtures")
    for path in get_ixp_metrics_from_moon_test_case_paths():

        def run(path=path):
            test_case = GetIxpMetricsFromMoonTestCase.parse_file(path)
            expected = get_ixp_summary_metrics(test_case.expected)
            actual = _raw_ixp_metrics_to_summary(
                field_group_name_to_field_ids=get_field_group_name_to_field_ids(
                    test_case.field_group_name_to_field_ids
                ),
                document_ids=tuple(
                    InternalCommentId(document_id)
                    for document_id in test_case.document_ids
                ),
                raw=get_raw_ixp_metrics_from_moon(test_case.raw),
                field_id_to_inherits_from={},
            )
            if actual != expected:
                diffs = _diff_dataclass(actual, expected)
                raise AssertionError(
                    f"{path.name}:\n  " + "\n  ".join(diffs[:20])
                )

        check(path.name, run)


# --- 3: test_ranged_value.py numeric table (verbatim expected numbers) ---

_RANGED_VALUE_CASES = [
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
    ((32, 42, 12), (20, 10, 22), 1.0, (1.6538462, 0.4716814), (86, 24.527433)),
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
    ((5, 3) * 10, (6, 3) * 10, 0.5767, (0.88888889, 0.01241184), (80, 1.1170656)),
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


def run_ranged_value_table() -> None:
    print("[3] ranged_value numeric table")
    # upstream test patches these module constants the same way
    original_min = ranged_value_module._MINIMUM_NUM_NON_ZERO_DENOMINATORS_FOR_VARIABILITY
    original_figs = ranged_value_module._NUM_SIGNIFICANT_FIGURES_FOR_VARIABILITY
    ranged_value_module._MINIMUM_NUM_NON_ZERO_DENOMINATORS_FOR_VARIABILITY = 2
    ranged_value_module._NUM_SIGNIFICANT_FIGURES_FOR_VARIABILITY = 8
    try:
        for i, (
            numerators,
            denominators,
            zero_division,
            (mean_value, mean_variability),
            (sum_value, sum_variability),
        ) in enumerate(_RANGED_VALUE_CASES):

            def run(
                numerators=numerators,
                denominators=denominators,
                zero_division=zero_division,
                mean_value=mean_value,
                mean_variability=mean_variability,
                sum_value=sum_value,
                sum_variability=sum_variability,
            ):
                actual_mean = RangedValue.from_mean(
                    numerators=numerators,
                    denominators=denominators,
                    zero_division_result=zero_division,
                )
                assert math.isclose(
                    actual_mean.value, mean_value, rel_tol=1e-6, abs_tol=1e-12
                ), (actual_mean.value, mean_value)
                assert actual_mean.variability == mean_variability, (
                    actual_mean.variability,
                    mean_variability,
                )
                actual_sum = RangedValue.from_sum(
                    counts=numerators, reference_counts=denominators
                )
                assert math.isclose(
                    actual_sum.value, sum_value, rel_tol=1e-6, abs_tol=1e-12
                ), (actual_sum.value, sum_value)
                assert actual_sum.variability == sum_variability, (
                    actual_sum.variability,
                    sum_variability,
                )

            check(f"ranged_value case {i}", run)

        def run_mismatched():
            for call in (
                lambda: RangedValue.from_mean(
                    numerators=(1, 2, 3),
                    denominators=(1, 2),
                    zero_division_result=0.0,
                ),
                lambda: RangedValue.from_sum(
                    counts=(1, 2, 3), reference_counts=(1, 2)
                ),
            ):
                try:
                    call()
                except AssertionError:
                    continue
                raise AssertionError("expected AssertionError")

        check("ranged_value mismatched lengths", run_mismatched)
    finally:
        ranged_value_module._MINIMUM_NUM_NON_ZERO_DENOMINATORS_FOR_VARIABILITY = original_min
        ranged_value_module._NUM_SIGNIFICANT_FIGURES_FOR_VARIABILITY = original_figs


# --- 4: typed-normalizer cases (from user-model tests/test_data_type.py) ---


def run_normalizer_cases() -> None:
    print("[4] typed-value normalizers")

    def bools():
        result = process_bool_field_value(" True ", None, None)
        assert result is not None
        assert result.formatted == "True"
        assert result.extraction == BoolExtraction(True)
        assert process_bool_field_value("b", None, None) is None

    def numbers():
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

    def money():
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

    def dates():
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

    def choices():
        # out-of-domain quirk (§4.5): without ALLOW_OUT_OF_DOMAIN two
        # DIFFERENT unmatched values both normalize to name=None → equal
        no_flags = frozenset()
        first = process_choice_field_value("apple", (), no_flags)
        second = process_choice_field_value("banana", (), no_flags)
        assert first is not None and second is not None
        assert first.extraction == ChoiceExtraction(name=None)
        assert first.extraction == second.extraction
        # with ALLOW_OUT_OF_DOMAIN the raw name is kept → not equal
        allow = frozenset({ChoiceFieldFlag.ALLOW_OUT_OF_DOMAIN})
        kept = process_choice_field_value("apple", (), allow)
        assert kept is not None
        assert kept.extraction == ChoiceExtraction(name="apple")

    def typed_equality():
        number = (ENTITY_DEF_ID_EXTRACTION_NUMBER,)
        # parsed == parsed even though raw differs
        assert moon_extractions_are_equal("1,000.00", "1000", number)
        # raw == raw still wins when parsing fails on both sides
        assert moon_extractions_are_equal("n/a", "n/a", number)
        assert not moon_extractions_are_equal("n/a", "none", number)
        # plain text is exact match only
        assert moon_extractions_are_equal("a", "a", ())
        assert not moon_extractions_are_equal("a", "A", ())
        assert moon_extractions_are_equal(None, None, ())
        assert not moon_extractions_are_equal("a", None, ())

    for name, fn in [
        ("bool normalizer", bools),
        ("number normalizer", numbers),
        ("money normalizer", money),
        ("date normalizer", dates),
        ("choice normalizer + out-of-domain quirk", choices),
        ("typed equality rules", typed_equality),
    ]:
        check(name, fn)


# --- 5: assignment solver differential vs scipy (optional) ---


def run_assignment_differential() -> None:
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment as scipy_lsa
    except ImportError:
        print("[5] assignment differential vs scipy — SKIPPED (no scipy)")
        return
    print("[5] assignment differential vs scipy")
    import random

    from ixp.assignment import linear_sum_assignment as ours

    def run():
        random.seed(20260713)
        for _ in range(2000):
            num_rows = random.randint(1, 8)
            num_cols = random.randint(1, 8)
            matrix = [
                [float(random.randint(0, 3)) for _ in range(num_cols)]
                for _ in range(num_rows)
            ]
            scipy_rows, scipy_cols = scipy_lsa(
                np.array(matrix, dtype=np.float32), maximize=True
            )
            our_rows, our_cols = ours(matrix, maximize=True)
            assert list(scipy_rows) == our_rows and list(scipy_cols) == our_cols, (
                matrix,
                (list(scipy_rows), list(scipy_cols)),
                (our_rows, our_cols),
            )

    check("2000 random tie-heavy matrices match scipy exactly", run)


def main() -> int:
    run_golden_ixp_metrics()
    run_golden_from_moon()
    run_ranged_value_table()
    run_normalizer_cases()
    run_assignment_differential()

    print()
    print(f"passed={PASSED} failed={FAILED}")
    if FAILURES:
        print()
        for failure in FAILURES[:10]:
            print("=" * 70)
            print(failure)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
