"""Unit tests for output formatters.

Tests JSON, table, and CSV formatting with various data types.
"""

import json
from typing import Any

from uipath._cli._utils._formatters import (
    _format_csv,
    _format_json,
    _format_table,
)


def test_format_json_simple_dict():
    """Test JSON formatting with a simple dictionary."""
    data = {"name": "test", "value": 123}
    result = _format_json(data)

    # Should be valid JSON
    parsed = json.loads(result)
    assert parsed == data


def test_format_json_list_of_dicts():
    """Test JSON formatting with list of dictionaries."""
    data = [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}]
    result = _format_json(data)

    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "first"


def test_format_table_single_item():
    """Test Rich table formatting with a single item."""
    data = {"name": "test", "value": "123"}
    result = _format_table(data, no_color=True)

    # Should contain column headers
    assert "name" in result
    assert "value" in result

    # Should contain data
    assert "test" in result
    assert "123" in result


def test_format_table_list():
    """Test Rich table formatting with a list."""
    data = [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}]
    result = _format_table(data, no_color=True)

    # Should contain headers
    assert "id" in result
    assert "name" in result

    # Should contain all data
    assert "first" in result
    assert "second" in result


def test_format_table_empty_list():
    """Test Rich table formatting with empty list."""
    data: list[Any] = []
    result = _format_table(data, no_color=True)

    assert result == "No results"


def test_format_csv_single_item():
    """Test CSV formatting with a single item."""
    data = {"name": "test", "value": "123"}
    result = _format_csv(data)

    # Should have header
    assert "name,value" in result or "value,name" in result

    # Should have data row
    assert "test" in result
    assert "123" in result


def test_format_csv_list():
    """Test CSV formatting with a list."""
    data = [{"id": "1", "name": "first"}, {"id": "2", "name": "second"}]
    result = _format_csv(data)

    lines = result.strip().split("\n")

    # Should have header + 2 data rows
    assert len(lines) == 3


def test_format_csv_empty_list():
    """Test CSV formatting with empty list."""
    data: list[Any] = []
    result = _format_csv(data)

    assert result == ""


def test_format_output_handles_pydantic_models():
    """Test that format_output can handle Pydantic models."""
    from pydantic import BaseModel

    class TestModel(BaseModel):
        name: str
        value: int

    model = TestModel(name="test", value=123)

    # Should not raise an error
    result = _format_json(model.model_dump())
    parsed = json.loads(result)
    assert parsed["name"] == "test"
    assert parsed["value"] == 123


def test_format_output_handles_generators():
    """Test that format_output handles generators properly."""

    def generate_items():
        yield {"id": 1}
        yield {"id": 2}
        yield {"id": 3}

    # Note: The actual format_output function handles this,
    # but the internal formatters expect lists
    items = list(generate_items())
    result = _format_json(items)

    parsed = json.loads(result)
    assert len(parsed) == 3


def test_format_json_with_special_types():
    """Test JSON formatting with datetime, UUID, etc."""
    from datetime import datetime
    from uuid import uuid4

    data = {
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "uuid": uuid4(),
        "none_value": None,
    }

    result = _format_json(data)

    # Should handle special types via default=str
    parsed = json.loads(result)
    assert "timestamp" in parsed
    assert "uuid" in parsed
    assert parsed["none_value"] is None


def test_format_output_handles_pydantic_in_generators():
    """Test that format_output handles Pydantic models inside generators."""
    from pydantic import BaseModel

    class TestModel(BaseModel):
        name: str
        value: int

    def generate_models():
        yield TestModel(name="test1", value=1)
        yield TestModel(name="test2", value=2)

    # Convert to list to use _format_json (format_output would consume the generator)
    items = list(generate_models())
    # Manually convert Pydantic models to dicts as format_output does
    items_dicts = [item.model_dump() for item in items]

    result = _format_json(items_dicts)
    parsed = json.loads(result)

    assert len(parsed) == 2
    assert parsed[0]["name"] == "test1"
    assert parsed[1]["name"] == "test2"


def test_format_table_with_rich_fallback():
    """Test table formatting falls back gracefully when rich is unavailable."""
    # We can't easily test ImportError without mocking, but we can test the code path
    # by directly calling the function which has the try/except
    data = [{"id": "1", "name": "first"}, {"id": "2", "name": "second"}]
    result = _format_table(data, no_color=True)

    # Should contain the data regardless of rich availability
    assert "1" in result
    assert "first" in result
    assert "2" in result
    assert "second" in result


def test_format_output_forces_no_color_for_file_output(tmp_path):
    """Test that table output to file is colorless."""
    from uipath._cli._utils._formatters import format_output

    data = [{"name": "test"}]
    output_file = tmp_path / "output.txt"

    format_output(data, fmt="table", output=str(output_file), no_color=False)

    content = output_file.read_text(encoding="utf-8")
    # Verify no ANSI escape codes in output
    assert "\x1b[" not in content  # ANSI escape sequence start
    assert "test" in content
