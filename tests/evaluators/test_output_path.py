"""Tests for resolve_output_path utility function.

Covers: wildcard, flat key, nested dot notation, array indexing,
mixed paths, error handling, and edge cases.
"""

import pytest

from uipath.eval._helpers.output_path import resolve_output_path


class TestResolveOutputPath:
    """Test suite for resolve_output_path."""

    # --- Wildcard ("*") ---

    def test_wildcard_returns_full_output_dict(self) -> None:
        output = {"a": 1, "b": 2}
        assert resolve_output_path(output, "*") == {"a": 1, "b": 2}

    def test_wildcard_returns_full_output_string(self) -> None:
        assert resolve_output_path("hello", "*") == "hello"

    def test_wildcard_returns_full_output_list(self) -> None:
        assert resolve_output_path([1, 2, 3], "*") == [1, 2, 3]

    # --- Flat key ---

    def test_flat_key_lookup(self) -> None:
        output = {"result": 42, "extra": "ignore"}
        assert resolve_output_path(output, "result") == 42

    def test_flat_key_returns_nested_dict(self) -> None:
        output = {"summary": {"total": 100, "count": 5}}
        assert resolve_output_path(output, "summary") == {"total": 100, "count": 5}

    # --- Nested dot notation ---

    def test_nested_dot_two_levels(self) -> None:
        output = {"summary": {"status": "completed"}}
        assert resolve_output_path(output, "summary.status") == "completed"

    def test_nested_dot_three_levels(self) -> None:
        output = {
            "customer": {
                "address": {
                    "city": "Springfield",
                }
            }
        }
        assert resolve_output_path(output, "customer.address.city") == "Springfield"

    def test_nested_dot_numeric_value(self) -> None:
        output = {"order": {"summary": {"total": 44.97}}}
        assert resolve_output_path(output, "order.summary.total") == 44.97

    # --- Array indexing ---

    def test_array_index_first(self) -> None:
        output = {"items": ["a", "b", "c"]}
        assert resolve_output_path(output, "items[0]") == "a"

    def test_array_index_last(self) -> None:
        output = {"items": ["a", "b", "c"]}
        assert resolve_output_path(output, "items[2]") == "c"

    def test_array_index_with_nested_property(self) -> None:
        output = {
            "items": [
                {"name": "Widget", "price": 9.99},
                {"name": "Gadget", "price": 24.99},
            ]
        }
        assert resolve_output_path(output, "items[0].name") == "Widget"
        assert resolve_output_path(output, "items[1].price") == 24.99

    def test_array_index_on_flat_array(self) -> None:
        output = {"tags": ["priority", "express", "verified"]}
        assert resolve_output_path(output, "tags[1]") == "express"

    # --- Mixed deep paths ---

    def test_mixed_nested_and_array(self) -> None:
        output = {
            "data": {
                "results": [
                    {"details": {"score": 95}},
                    {"details": {"score": 87}},
                ]
            }
        }
        assert resolve_output_path(output, "data.results[0].details.score") == 95
        assert resolve_output_path(output, "data.results[1].details.score") == 87

    def test_deeply_nested_array_of_arrays(self) -> None:
        output = {"matrix": [[1, 2], [3, 4]]}
        assert resolve_output_path(output, "matrix[0][1]") == 2
        assert resolve_output_path(output, "matrix[1][0]") == 3

    # --- Error handling ---

    def test_missing_key_raises_key_error(self) -> None:
        output = {"a": 1}
        with pytest.raises(KeyError):
            resolve_output_path(output, "missing_key")

    def test_missing_nested_key_raises_key_error(self) -> None:
        output = {"a": {"b": 1}}
        with pytest.raises(KeyError):
            resolve_output_path(output, "a.missing")

    def test_array_index_out_of_range(self) -> None:
        output = {"items": [1, 2]}
        with pytest.raises(IndexError):
            resolve_output_path(output, "items[5]")

    def test_index_on_non_list_raises_type_error(self) -> None:
        output = {"value": "string"}
        with pytest.raises(TypeError):
            resolve_output_path(output, "value[0]")

    def test_key_on_non_dict_raises_type_error(self) -> None:
        output = {"value": 42}
        with pytest.raises(TypeError):
            resolve_output_path(output, "value.nested")

    def test_invalid_empty_path_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            resolve_output_path({"a": 1}, "")

    # --- Edge cases ---

    def test_output_is_none(self) -> None:
        assert resolve_output_path(None, "*") is None

    def test_path_with_numeric_string_key(self) -> None:
        output = {"123": "numeric-key"}
        assert resolve_output_path(output, "123") == "numeric-key"

    def test_nested_none_value(self) -> None:
        output = {"a": {"b": None}}
        assert resolve_output_path(output, "a.b") is None

    def test_empty_dict_value(self) -> None:
        output = {"a": {}}
        assert resolve_output_path(output, "a") == {}

    def test_bool_value(self) -> None:
        output = {"active": True}
        assert resolve_output_path(output, "active") is True
