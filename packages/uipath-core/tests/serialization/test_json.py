"""Tests for serialization utilities."""

import json
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel

from uipath.core.serialization import serialize_json


def _has_tzdata() -> bool:
    """Check if timezone data is available."""
    try:
        ZoneInfo("America/New_York")
        return True
    except Exception:
        return False


class Color(Enum):
    """Test enum."""

    RED = "red"
    GREEN = "green"
    BLUE = 3


class Priority(Enum):
    """Test enum with int values."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class SimpleModel(BaseModel):
    """Simple Pydantic v2 model."""

    name: str
    value: int


class NestedModel(BaseModel):
    """Pydantic model with nested model."""

    id: str
    inner: SimpleModel
    items: list[SimpleModel]


@dataclass
class SimpleDataclass:
    """Simple dataclass for testing."""

    name: str
    count: int


@dataclass
class NestedDataclass:
    """Dataclass with nested dataclass."""

    id: str
    inner: SimpleDataclass


Point = namedtuple("Point", ["x", "y"])


class TestSimpleSerializeDefaults:
    """Tests for serialize_defaults and serialize_json functions."""

    def test_serializes_none(self) -> None:
        """Test None serialization via json.dumps."""
        data = {"value": None}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["value"] is None

    def test_serializes_primitives(self) -> None:
        """Test primitive types pass through json.dumps unchanged."""
        data = {
            "bool_true": True,
            "bool_false": False,
            "integer": 42,
            "float": 3.14,
            "string": "hello",
        }
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["bool_true"] is True
        assert parsed["bool_false"] is False
        assert parsed["integer"] == 42
        assert parsed["float"] == 3.14
        assert parsed["string"] == "hello"

    def test_serializes_pydantic_model(self) -> None:
        """Test Pydantic BaseModel serialization via json.dumps."""
        model = SimpleModel(name="test", value=42)
        result = serialize_json(model)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["name"] == "test"
        assert parsed["value"] == 42

    def test_serializes_nested_pydantic_model(self) -> None:
        """Test nested Pydantic models via json.dumps."""
        inner = SimpleModel(name="inner", value=10)
        model = NestedModel(
            id="123",
            inner=inner,
            items=[
                SimpleModel(name="item1", value=1),
                SimpleModel(name="item2", value=2),
            ],
        )
        result = serialize_json(model)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["id"] == "123"
        assert parsed["inner"]["name"] == "inner"
        assert len(parsed["items"]) == 2
        assert parsed["items"][0]["name"] == "item1"
        assert parsed["items"][1]["value"] == 2

    def test_serializes_pydantic_model_excludes_none(self) -> None:
        """Test Pydantic model with None values excluded via json.dumps."""

        class OptionalModel(BaseModel):
            required: str
            optional: str | None = None

        model = OptionalModel(required="value")
        result = serialize_json(model)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["required"] == "value"
        # exclude_none=True should exclude the None field
        assert "optional" not in parsed

    def test_serializes_pydantic_model_class(self) -> None:
        """Test Pydantic model class (not instance) serialization via json.dumps."""
        data = {"model_class": SimpleModel}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert isinstance(parsed["model_class"], dict)
        assert parsed["model_class"]["__class__"] == "SimpleModel"
        assert parsed["model_class"]["__module__"] == "test_json"
        assert "schema" in parsed["model_class"]
        assert isinstance(parsed["model_class"]["schema"], dict)

    def test_serializes_dataclass(self) -> None:
        """Test dataclass serialization via json.dumps."""
        obj = SimpleDataclass(name="test", count=5)
        result = serialize_json(obj)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["name"] == "test"
        assert parsed["count"] == 5

    def test_serializes_nested_dataclass(self) -> None:
        """Test nested dataclass serialization via json.dumps."""
        inner = SimpleDataclass(name="inner", count=10)
        obj = NestedDataclass(id="123", inner=inner)
        result = serialize_json(obj)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["id"] == "123"
        assert parsed["inner"]["name"] == "inner"
        assert parsed["inner"]["count"] == 10

    def test_serializes_enum_string_value(self) -> None:
        """Test enum with string value via json.dumps."""
        data = {"color": Color.RED}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["color"] == "red"

    def test_serializes_enum_int_value(self) -> None:
        """Test enum with int value via json.dumps."""
        data = {"priority": Priority.HIGH}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["priority"] == 3

    def test_serializes_enum_mixed_value(self) -> None:
        """Test enum with mixed types via json.dumps."""
        data = {"color1": Color.GREEN, "color2": Color.BLUE}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["color1"] == "green"
        assert parsed["color2"] == 3

    def test_serializes_datetime(self) -> None:
        """Test datetime serialization via json.dumps."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        data = {"timestamp": dt}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert isinstance(parsed["timestamp"], str)
        assert "2024-01-15" in parsed["timestamp"]
        assert "10:30:45" in parsed["timestamp"]

    def test_serializes_datetime_with_timezone(self) -> None:
        """Test datetime with timezone via json.dumps."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        data = {"timestamp": dt}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert isinstance(parsed["timestamp"], str)
        assert parsed["timestamp"] == "2024-01-15T10:30:45+00:00"

    def test_serializes_timezone(self) -> None:
        """Test timezone object serialization via json.dumps."""
        tz = timezone.utc
        data = {"timezone": tz}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["timezone"] == "UTC"

    @pytest.mark.skipif(not _has_tzdata(), reason="Timezone data not available")
    def test_serializes_zoneinfo(self) -> None:
        """Test ZoneInfo serialization via json.dumps."""
        tz = ZoneInfo("America/New_York")
        data = {"timezone": tz}
        result = serialize_json(data)
        parsed = json.loads(result)
        # ZoneInfo returns timezone name or None
        assert isinstance(parsed["timezone"], (str, type(None)))

    def test_serializes_set(self) -> None:
        """Test set serialization via json.dumps."""
        obj = {1, 2, 3}
        data = {"numbers": obj}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert isinstance(parsed["numbers"], list)
        assert set(parsed["numbers"]) == {1, 2, 3}

    def test_serializes_tuple(self) -> None:
        """Test tuple serialization via json.dumps."""
        obj = (1, 2, 3)
        data = {"numbers": obj}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert isinstance(parsed["numbers"], list)
        assert parsed["numbers"] == [1, 2, 3]

    def test_serializes_named_tuple(self) -> None:
        """Test named tuple serialization via json.dumps.

        Note: Python's json encoder treats namedtuples as regular tuples,
        so they serialize as lists [x, y] rather than dicts {"x": x, "y": y}.
        The serialize_defaults function is not called for namedtuples
        because they're natively JSON-serializable as tuples.
        """
        point = Point(x=10, y=20)
        data = {"point": point}
        result = serialize_json(data)
        parsed = json.loads(result)
        # Namedtuples serialize as lists through json.dumps
        assert isinstance(parsed["point"], list)
        assert parsed["point"] == [10, 20]

    def test_serializes_object_with_as_dict(self) -> None:
        """Test object with as_dict property via json.dumps."""

        class RuntimeLike:
            @property
            def as_dict(self) -> dict[str, Any]:
                return {"host": "localhost", "port": 8080}

        obj = RuntimeLike()
        data = {"runtime": obj}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["runtime"] == {"host": "localhost", "port": 8080}

    def test_serializes_object_with_to_dict(self) -> None:
        """Test object with to_dict method via json.dumps."""

        class CustomObject:
            def to_dict(self) -> dict[str, Any]:
                return {"custom": "value"}

        obj = CustomObject()
        data = {"obj": obj}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["obj"] == {"custom": "value"}

    def test_serializes_unknown_object_to_str(self) -> None:
        """Test unknown object falls back to str() via json.dumps."""

        class CustomClass:
            def __str__(self) -> str:
                return "custom_string"

        obj = CustomClass()
        data = {"obj": obj}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["obj"] == "custom_string"

    def test_serializes_exception(self) -> None:
        """Test Exception serialization via json.dumps."""
        err = ValueError("something went wrong")
        data = {"error": err}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["error"] == "something went wrong"

    def test_with_json_dumps(self) -> None:
        """Test integration with json.dumps()."""

        class ComplexObject(BaseModel):
            name: str
            created_at: datetime
            priority: Priority

        obj = ComplexObject(
            name="task",
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.HIGH,
        )

        # Should not raise TypeError
        result = serialize_json(obj)
        parsed = json.loads(result)

        assert parsed["name"] == "task"
        assert "2024-01-15" in parsed["created_at"]
        assert parsed["priority"] == 3

    def test_with_json_dumps_complex_nested(self) -> None:
        """Test with complex nested structure."""
        data = {
            "model": SimpleModel(name="test", value=42),
            "dataclass": SimpleDataclass(name="dc", count=5),
            "enum": Color.RED,
            "datetime": datetime(2024, 1, 1),
            "set": {1, 2, 3},
            "tuple": (4, 5, 6),
            "error": ValueError("something failed"),
        }

        result = serialize_json(data)
        parsed = json.loads(result)

        assert parsed["model"]["name"] == "test"
        assert parsed["dataclass"]["name"] == "dc"
        assert parsed["enum"] == "red"
        assert "2024-01-01" in parsed["datetime"]
        assert set(parsed["set"]) == {1, 2, 3}
        assert parsed["tuple"] == [4, 5, 6]
        assert parsed["error"] == "something failed"

    def test_with_list_of_pydantic_models(self) -> None:
        """Test with list of Pydantic models (common MCP scenario)."""
        models = [
            SimpleModel(name="first", value=1),
            SimpleModel(name="second", value=2),
            SimpleModel(name="third", value=3),
        ]

        # This should not raise TypeError
        result = serialize_json(models)
        parsed = json.loads(result)

        assert len(parsed) == 3
        assert parsed[0]["name"] == "first"
        assert parsed[1]["value"] == 2

    def test_recursive_enum_serialization(self) -> None:
        """Test that enum values are recursively serialized via json.dumps."""

        class NestedEnum(Enum):
            """Enum with complex value."""

            COMPLEX = {"key": "value"}

        data = {"enum": NestedEnum.COMPLEX}
        result = serialize_json(data)
        parsed = json.loads(result)
        # The enum value itself (a dict) should be returned as-is
        assert parsed["enum"] == {"key": "value"}
        assert isinstance(parsed["enum"], dict)

    def test_dataclass_class_returns_string(self) -> None:
        """Test that dataclass class (not instance) falls back to str via json.dumps."""
        data = {"dataclass_class": SimpleDataclass}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert isinstance(parsed["dataclass_class"], str)
        assert "SimpleDataclass" in parsed["dataclass_class"]

    def test_empty_collections(self) -> None:
        """Test empty collections via json.dumps."""
        data: dict[str, Any] = {"empty_set": set(), "empty_tuple": (), "empty_list": []}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["empty_set"] == []
        assert parsed["empty_tuple"] == []
        assert parsed["empty_list"] == []

    def test_with_dict_method(self) -> None:
        """Test object with dict() method (Pydantic v1 compatibility) via json.dumps."""

        class OldStyleModel:
            def dict(self) -> dict[str, Any]:
                return {"old": "style"}

        obj = OldStyleModel()
        data = {"obj": obj}
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed["obj"] == {"old": "style"}

    def test_dict_of_pydantic_models(self) -> None:
        """Test dictionary containing Pydantic models as values."""
        data = {
            "user1": SimpleModel(name="Alice", value=100),
            "user2": SimpleModel(name="Bob", value=200),
            "user3": SimpleModel(name="Charlie", value=300),
        }

        result = serialize_json(data)
        parsed = json.loads(result)

        assert isinstance(parsed, dict)
        assert parsed["user1"]["name"] == "Alice"
        assert parsed["user1"]["value"] == 100
        assert parsed["user2"]["name"] == "Bob"
        assert parsed["user2"]["value"] == 200
        assert parsed["user3"]["name"] == "Charlie"
        assert parsed["user3"]["value"] == 300

    def test_dict_of_dataclass_models(self) -> None:
        """Test dictionary containing dataclass instances as values."""
        data = {
            "item1": SimpleDataclass(name="First", count=1),
            "item2": SimpleDataclass(name="Second", count=2),
            "item3": SimpleDataclass(name="Third", count=3),
        }

        result = serialize_json(data)
        parsed = json.loads(result)

        assert isinstance(parsed, dict)
        assert parsed["item1"]["name"] == "First"
        assert parsed["item1"]["count"] == 1
        assert parsed["item2"]["name"] == "Second"
        assert parsed["item2"]["count"] == 2
        assert parsed["item3"]["name"] == "Third"
        assert parsed["item3"]["count"] == 3

    def test_normal_class_fallback_to_str(self) -> None:
        """Test normal class (not Pydantic, dataclass, or enum) falls back to str()."""

        class RegularClass:
            def __init__(self, value: str) -> None:
                self.value = value

            def __str__(self) -> str:
                return f"RegularClass({self.value})"

        obj = RegularClass("test_value")
        data = {"object": obj, "name": "test"}
        json_result = serialize_json(data)
        parsed = json.loads(json_result)
        assert parsed["object"] == "RegularClass(test_value)"
        assert parsed["name"] == "test"

    def test_list_of_dataclass(self) -> None:
        """Test list containing dataclass instances."""
        data = [
            SimpleDataclass(name="First", count=1),
            SimpleDataclass(name="Second", count=2),
            SimpleDataclass(name="Third", count=3),
        ]

        result = serialize_json(data)
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 3
        assert parsed[0]["name"] == "First"
        assert parsed[0]["count"] == 1
        assert parsed[1]["name"] == "Second"
        assert parsed[2]["count"] == 3

    def test_list_of_pydantic_models(self) -> None:
        """Test list containing Pydantic model instances."""
        data = [
            SimpleModel(name="Alice", value=100),
            SimpleModel(name="Bob", value=200),
            SimpleModel(name="Charlie", value=300),
        ]

        result = serialize_json(data)
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 3
        assert parsed[0]["name"] == "Alice"
        assert parsed[0]["value"] == 100
        assert parsed[1]["name"] == "Bob"
        assert parsed[2]["value"] == 300

    def test_list_of_normal_classes(self) -> None:
        """Test list containing normal class instances (fallback to str)."""

        class Item:
            def __init__(self, id: int, label: str) -> None:
                self.id = id
                self.label = label

            def __str__(self) -> str:
                return f"Item(id={self.id}, label={self.label})"

        data = [
            Item(1, "First"),
            Item(2, "Second"),
            Item(3, "Third"),
        ]

        result = serialize_json(data)
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 3
        assert parsed[0] == "Item(id=1, label=First)"
        assert parsed[1] == "Item(id=2, label=Second)"
        assert parsed[2] == "Item(id=3, label=Third)"

    def test_list_of_mixed_types(self) -> None:
        """Test list containing mixed types: Pydantic, dataclass, normal class, primitives."""

        class CustomItem:
            def __init__(self, name: str) -> None:
                self.name = name

            def __str__(self) -> str:
                return f"CustomItem({self.name})"

        data = [
            SimpleModel(name="pydantic", value=1),
            SimpleDataclass(name="dataclass", count=2),
            CustomItem("custom"),
            "plain_string",
            42,
            True,
            None,
            Color.RED,
        ]

        result = serialize_json(data)
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 8
        # Pydantic model
        assert parsed[0]["name"] == "pydantic"
        assert parsed[0]["value"] == 1
        # Dataclass
        assert parsed[1]["name"] == "dataclass"
        assert parsed[1]["count"] == 2
        # Normal class (str fallback)
        assert parsed[2] == "CustomItem(custom)"
        # Primitives
        assert parsed[3] == "plain_string"
        assert parsed[4] == 42
        assert parsed[5] is True
        assert parsed[6] is None
        # Enum
        assert parsed[7] == "red"

    def test_list_of_lists_mixed(self) -> None:
        """Test nested lists containing mixed types."""

        class Widget:
            def __init__(self, id: int) -> None:
                self.id = id

            def __str__(self) -> str:
                return f"Widget({self.id})"

        data = [
            [SimpleModel(name="model1", value=1), SimpleModel(name="model2", value=2)],
            [
                SimpleDataclass(name="dc1", count=10),
                SimpleDataclass(name="dc2", count=20),
            ],
            [Widget(1), Widget(2), Widget(3)],
            ["string1", "string2"],
            [1, 2, 3, 4],
            [Color.RED, Color.GREEN, Priority.HIGH],
            [True, False, None],
        ]

        result = serialize_json(data)
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 7

        # First sublist: Pydantic models
        assert len(parsed[0]) == 2
        assert parsed[0][0]["name"] == "model1"
        assert parsed[0][1]["value"] == 2

        # Second sublist: Dataclasses
        assert len(parsed[1]) == 2
        assert parsed[1][0]["name"] == "dc1"
        assert parsed[1][1]["count"] == 20

        # Third sublist: Normal classes
        assert len(parsed[2]) == 3
        assert parsed[2][0] == "Widget(1)"
        assert parsed[2][2] == "Widget(3)"

        # Fourth sublist: Strings
        assert parsed[3] == ["string1", "string2"]

        # Fifth sublist: Integers
        assert parsed[4] == [1, 2, 3, 4]

        # Sixth sublist: Enums
        assert parsed[5] == ["red", "green", 3]

        # Seventh sublist: Booleans and None
        assert parsed[6] == [True, False, None]
