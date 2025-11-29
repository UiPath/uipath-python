from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from uipath._cli._utils._common import serialize_object


class SamplePydanticModel(BaseModel):
    """Sample Pydantic model for serialization testing."""

    name: str
    age: int
    tags: list[str]
    metadata: dict[str, Any] | None = None


@dataclass
class SampleDataClass:
    """Sample dataclass for serialization testing."""

    value: str
    numbers: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "numbers": self.numbers}


def test_serialize_primitive_types() -> None:
    """Test serialization of primitive data types."""
    assert serialize_object(42) == 42
    assert serialize_object("test") == "test"
    assert serialize_object(True)
    assert serialize_object(None) is None
    assert serialize_object(3.14) == 3.14


def test_serialize_list() -> None:
    """Test serialization of lists with mixed content."""
    test_list = [1, "two", {"three": 3}, [4, 5]]
    expected = [1, "two", {"three": 3}, [4, 5]]
    assert serialize_object(test_list) == expected


def test_serialize_dict() -> None:
    """Test serialization of nested dictionaries."""
    test_dict = {
        "string": "value",
        "number": 42,
        "nested": {"key": "value"},
        "list": [1, 2, 3],
    }
    expected = {
        "string": "value",
        "number": 42,
        "nested": {"key": "value"},
        "list": [1, 2, 3],
    }
    assert serialize_object(test_dict) == expected


def test_serialize_pydantic_model() -> None:
    """Test serialization of Pydantic models with nested structures."""
    model = SamplePydanticModel(
        name="test", age=25, tags=["tag1", "tag2"], metadata={"key": "value"}
    )
    expected = {
        "name": "test",
        "age": 25,
        "tags": ["tag1", "tag2"],
        "metadata": {"key": "value"},
    }
    assert serialize_object(model) == expected


def test_serialize_dataclass() -> None:
    """Test serialization of dataclass with to_dict method."""
    data = SampleDataClass(value="test", numbers=[1, 2, 3])
    expected = {"value": "test", "numbers": [1, 2, 3]}
    assert serialize_object(data) == expected


def test_serialize_iterable() -> None:
    """Test serialization of custom iterable objects."""
    # Using a set as an example of an iterable
    test_set = {("key1", "value1"), ("key2", "value2")}
    expected = {"key1": "value1", "key2": "value2"}
    assert serialize_object(test_set) == expected


def test_serialize_complex_nested_structure() -> None:
    """Test serialization of complex nested structure with mixed types."""
    complex_structure = {
        "model": SamplePydanticModel(
            name="test", age=25, tags=["tag1", "tag2"], metadata={"nested": True}
        ),
        "dataclass": SampleDataClass(value="test", numbers=[1, 2, 3]),
        "list": [
            {"key": "value"},
            SamplePydanticModel(name="nested", age=30, tags=["tag3"]),
            [1, 2, 3],
        ],
    }

    expected = {
        "model": {
            "name": "test",
            "age": 25,
            "tags": ["tag1", "tag2"],
            "metadata": {"nested": True},
        },
        "dataclass": {"value": "test", "numbers": [1, 2, 3]},
        "list": [
            {"key": "value"},
            {"name": "nested", "age": 30, "tags": ["tag3"], "metadata": None},
            [1, 2, 3],
        ],
    }
    assert serialize_object(complex_structure) == expected
