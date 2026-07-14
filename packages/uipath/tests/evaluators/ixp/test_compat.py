"""Behavior locks for the _compat shim and the assignment solver.

These pin the upstream-faithful edge cases the golden fixtures don't reach:
the FrozenDict API surface, the rounding helpers, whitespace normalization
(including the regex-module parity on U+001C-U+001F), EntityDefId, and the
assignment solver's transpose/infeasible branches.
"""

from __future__ import annotations

import pickle

import pytest

from uipath.eval.evaluators.ixp._compat import (
    EntityDefId,
    FrozenDict,
    normalize_all_spaces,
    round_like_javascript,
    round_to_significant_figures,
)
from uipath.eval.evaluators.ixp.assignment import linear_sum_assignment


def test_frozendict_construction_and_mapping() -> None:
    frozen = FrozenDict({"a": 1, "b": 2})
    assert frozen["a"] == 1
    assert len(frozen) == 2
    assert set(iter(frozen)) == {"a", "b"}
    assert dict(frozen.items()) == {"a": 1, "b": 2}
    assert set(frozen.keys()) == {"a", "b"}
    assert sorted(frozen.values()) == [1, 2]
    assert "FrozenDict" in repr(frozen)


def test_frozendict_empty_singleton_and_identity() -> None:
    assert FrozenDict() is FrozenDict()
    assert FrozenDict({}) is FrozenDict()
    assert hash(FrozenDict()) == 0
    existing = FrozenDict({"a": 1})
    assert FrozenDict(existing) is existing


def test_frozendict_hash_is_order_insensitive() -> None:
    assert hash(FrozenDict({"a": 1, "b": 2})) == hash(FrozenDict({"b": 2, "a": 1}))
    # mapping and iterable-of-pairs constructors produce equal instances
    assert FrozenDict({"a": 1}) == FrozenDict([("a", 1)])
    assert FrozenDict({"a": 1}) != FrozenDict({"a": 2})
    # hash is cached after first computation and stays stable
    frozen = FrozenDict({"a": 1})
    first_hash = hash(frozen)
    assert hash(frozen) == first_hash


def test_frozendict_update_discard_set_return_new_instances() -> None:
    frozen = FrozenDict({"a": 1})
    updated = frozen.update({"b": 2})
    assert dict(updated) == {"a": 1, "b": 2}
    assert dict(frozen) == {"a": 1}
    empty: FrozenDict[str, int] = FrozenDict()
    assert dict(empty.update({"x": 9})) == {"x": 9}

    assert dict(frozen.set("c", 3)) == {"a": 1, "c": 3}
    assert frozen.discard("missing") is frozen
    assert dict(updated.discard("a")) == {"b": 2}


def test_frozendict_pickle_roundtrip() -> None:
    # safe: round-trips an object constructed in this test, no external data
    frozen = FrozenDict({"a": 1, "b": 2})
    assert pickle.loads(pickle.dumps(frozen)) == frozen


def test_rounding_helpers() -> None:
    assert round_to_significant_figures(0.0, 3) == 0.0
    assert round_to_significant_figures(0.0123456, 3) == 0.0123
    assert round_to_significant_figures(-0.0123456, 3) == -0.0123
    assert round_to_significant_figures(98765.0, 2) == 99000.0
    # JS-style rounding: ties toward +infinity
    assert round_like_javascript(0.125, 2) == 0.13
    assert round_like_javascript(-0.125, 2) == -0.12
    assert round_like_javascript(2.675, 2) == 2.68


def test_normalize_all_spaces() -> None:
    assert normalize_all_spaces("  a \t b\n c  ") == "a b c"
    assert normalize_all_spaces("a​ b") == "a b"
    # regex-module \s parity: U+001C-U+001F are NOT whitespace upstream,
    # so interior occurrences must be preserved
    assert normalize_all_spaces("USD\x1c1,234.50") == "USD\x1c1,234.50"
    assert normalize_all_spaces(" \x1cabc\x1c ") == "abc"


def test_entity_def_id() -> None:
    assert EntityDefId.from_int(7).hex_value == "0000000000000007"
    assert EntityDefId.builtin_from_int(6) == EntityDefId.from_int(6)
    with pytest.raises(AssertionError):
        EntityDefId("not-hex")


def test_assignment_transposed_and_edge_cases() -> None:
    # more rows than columns exercises the transpose branch
    rows, cols = linear_sum_assignment([[1.0], [2.0], [3.0]], maximize=True)
    assert rows == [2] and cols == [0]
    rows, cols = linear_sum_assignment(
        [[9.0, 1.0], [1.0, 9.0], [5.0, 5.0]], maximize=True
    )
    assert rows == [0, 1] and cols == [0, 1]
    # minimize mode (the scipy default) on a square matrix
    rows, cols = linear_sum_assignment([[4.0, 1.0], [2.0, 8.0]])
    assert rows == [0, 1] and cols == [1, 0]
    # empty input
    assert linear_sum_assignment([]) == ([], [])


def test_assignment_infeasible_raises() -> None:
    infinity = float("inf")
    with pytest.raises(ValueError):
        linear_sum_assignment([[infinity, infinity]], maximize=False)
