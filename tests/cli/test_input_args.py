"""Test input args generation functionality."""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from uipath._cli._utils._input_args import get_type_schema


class EventArguments(BaseModel):
    """Test Pydantic model with aliases for testing."""

    event_connector: Optional[str] = Field(default=None, alias="UiPathEventConnector")
    event: Optional[str] = Field(default=None, alias="UiPathEvent")
    event_object_type: Optional[str] = Field(
        default=None, alias="UiPathEventObjectType"
    )
    event_object_id: Optional[str] = Field(default=None, alias="UiPathEventObjectId")
    additional_event_data: Optional[str] = Field(
        default=None, alias="UiPathAdditionalEventData"
    )


class RequiredFieldsModel(BaseModel):
    """Test Pydantic model with required and optional fields."""

    required_field: str
    optional_field: Optional[str] = None
    aliased_required: int = Field(alias="AliasedRequired")
    aliased_optional: Optional[int] = Field(default=100, alias="AliasedOptional")


@dataclass
class SimpleDataClass:
    """Test dataclass for comparison."""

    name: str
    value: int = 42


def test_pydantic_model_with_aliases():
    """Test that Pydantic model schemas use field aliases when defined."""
    schema = get_type_schema(EventArguments)

    assert schema["type"] == "object"
    assert "properties" in schema

    # Check that aliases are used in property names
    expected_properties = {
        "UiPathEventConnector",
        "UiPathEvent",
        "UiPathEventObjectType",
        "UiPathEventObjectId",
        "UiPathAdditionalEventData",
    }
    actual_properties = set(schema["properties"].keys())
    assert actual_properties == expected_properties

    # All fields have defaults, so none should be required
    assert schema["required"] == []


def test_pydantic_model_required_fields():
    """Test that required fields are correctly identified in Pydantic models."""
    schema = get_type_schema(RequiredFieldsModel)

    assert schema["type"] == "object"
    assert "properties" in schema

    # Check properties include both field names and aliases
    expected_properties = {
        "required_field",  # field name (no alias)
        "optional_field",  # field name (no alias)
        "AliasedRequired",  # alias
        "AliasedOptional",  # alias
    }
    actual_properties = set(schema["properties"].keys())
    assert actual_properties == expected_properties

    # Check required fields (using aliases where defined)
    expected_required = {"required_field", "AliasedRequired"}
    actual_required = set(schema["required"])
    assert actual_required == expected_required


def test_dataclass_still_works():
    """Test that dataclass functionality is not broken."""
    schema = get_type_schema(SimpleDataClass)

    assert schema["type"] == "object"
    assert "properties" in schema

    # Dataclass should use field names (no alias support)
    expected_properties = {"name", "value"}
    actual_properties = set(schema["properties"].keys())
    assert actual_properties == expected_properties

    # Field with default should not be required
    assert schema["required"] == ["name"]


def test_primitive_types():
    """Test that primitive type handling still works."""
    assert get_type_schema(str) == {"type": "string"}
    assert get_type_schema(int) == {"type": "integer"}
    assert get_type_schema(float) == {"type": "number"}
    assert get_type_schema(bool) == {"type": "boolean"}


def test_optional_types():
    """Test handling of Optional types."""
    schema = get_type_schema(Optional[str])
    assert schema == {"type": "string"}  # Should unwrap Optional
