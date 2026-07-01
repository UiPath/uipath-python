"""Tests for the shared governance payload helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from uipath.core.adapters import (
    MODEL_TEXT_CAP,
    coerce_args,
    join_within_cap,
    stringify,
)


def test_join_within_cap_joins_and_skips_empty():
    assert join_within_cap(["a", "", "b"]) == "a\nb"
    assert join_within_cap(["a", "b"], sep=" ") == "a b"


def test_join_within_cap_bounds_result_at_cap():
    assert len(join_within_cap(["x" * 100, "y" * 100], cap=50)) <= 50


def test_join_within_cap_stops_once_budget_exhausted():
    out = join_within_cap(["x" * 50, "TAIL"], cap=50)
    assert "TAIL" not in out


def test_stringify_str_passthrough_capped():
    assert stringify("hello") == "hello"
    assert len(stringify("x" * (MODEL_TEXT_CAP + 100))) <= MODEL_TEXT_CAP


def test_stringify_dict_is_json():
    assert "balance" in stringify({"balance": 1000})


def test_stringify_circular_falls_back_to_str():
    circular: dict[str, Any] = {}
    circular["self"] = circular
    assert isinstance(stringify(circular), str)


def test_stringify_caps_large_payload():
    assert len(stringify({"blob": "x" * (MODEL_TEXT_CAP + 5000)})) <= MODEL_TEXT_CAP


def test_coerce_args_none_and_mapping():
    assert coerce_args(None) == {}
    assert coerce_args({"a": 1}) == {"a": 1}


def test_coerce_args_json_string():
    assert coerce_args('{"a": 1}') == {"a": 1}
    assert coerce_args("[1, 2]") == {"_": [1, 2]}  # non-dict JSON preserved
    assert coerce_args("not json") == {"_raw": "not json"}  # malformed preserved


def test_coerce_args_pydantic_like_model_dump():
    assert coerce_args(SimpleNamespace(model_dump=lambda: {"b": 2})) == {"b": 2}


def test_coerce_args_model_dump_failure_warns_and_empties(caplog):
    def _bad() -> dict[str, Any]:
        raise ValueError("boom")

    import logging

    with caplog.at_level(logging.WARNING):
        assert coerce_args(SimpleNamespace(model_dump=_bad)) == {}
    assert any("model_dump()" in r.message for r in caplog.records)


def test_coerce_args_other_value_preserved_under_underscore():
    assert coerce_args(["a", "b"]) == {"_": ["a", "b"]}
