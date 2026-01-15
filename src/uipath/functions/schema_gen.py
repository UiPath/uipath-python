"""Type hint to JSON schema conversion utilities."""

import inspect
from dataclasses import fields, is_dataclass
from enum import Enum
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

TYPE_MAP: dict[str, str] = {
    "int": "integer",
    "float": "number",
    "str": "string",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "List": "array",
    "Dict": "object",
}


def get_type_schema(type_hint: Any) -> dict[str, Any]:
    """Convert a type hint to a JSON schema."""
    if type_hint is None or type_hint == inspect.Parameter.empty:
        return {"type": "object"}

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Handle Optional[T] / Union[T, None]
    if origin is Union or origin is UnionType:
        # Filter out None/NoneType from the union
        non_none_args = [arg for arg in args if arg is not type(None)]

        if len(non_none_args) == 1:
            return get_type_schema(non_none_args[0])
        return {"type": "object"}

    # Handle list/List
    if origin in (list, tuple) or (
        hasattr(origin, "__name__") and origin.__name__ == "List"
    ):
        item_type = args[0] if args else Any
        return {"type": "array", "items": get_type_schema(item_type)}

    # Handle dict/Dict
    if origin is dict or (hasattr(origin, "__name__") and origin.__name__ == "Dict"):
        return {"type": "object"}

    if not inspect.isclass(type_hint):
        type_name = getattr(type_hint, "__name__", str(type_hint))
        return {"type": TYPE_MAP.get(type_name, "object")}

    # Handle Enum
    if issubclass(type_hint, Enum):
        return _get_enum_schema(type_hint)

    # Handle Pydantic models
    if issubclass(type_hint, BaseModel):
        return _get_pydantic_schema(type_hint)

    # Handle dataclasses
    if is_dataclass(type_hint):
        return _get_dataclass_schema(type_hint)

    # Handle regular classes with annotations
    if hasattr(type_hint, "__annotations__"):
        return _get_annotated_class_schema(type_hint)

    # Fallback
    type_name = getattr(type_hint, "__name__", str(type_hint))
    return {"type": TYPE_MAP.get(type_name, "object")}


def _get_enum_schema(enum_class: type[Enum]) -> dict[str, Any]:
    """Generate schema for Enum types."""
    enum_values = [member.value for member in enum_class]
    if not enum_values:
        return {"type": "string", "enum": []}

    first_value = enum_values[0]
    enum_type = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }.get(type(first_value), "string")

    return {"type": enum_type, "enum": enum_values}


def _get_pydantic_schema(model_class: type[BaseModel]) -> dict[str, Any]:
    """Generate schema for Pydantic models."""
    properties = {}
    required = []

    for field_name, field_info in model_class.model_fields.items():
        schema_field_name = field_info.alias or field_name
        properties[schema_field_name] = get_type_schema(field_info.annotation)
        if field_info.is_required():
            required.append(schema_field_name)

    return {"type": "object", "properties": properties, "required": required}


def _get_dataclass_schema(dataclass_type: type) -> dict[str, Any]:
    """Generate schema for dataclass types."""
    properties = {}
    required = []

    for field in fields(dataclass_type):
        properties[field.name] = get_type_schema(field.type)
        # Field is required if it has no default value and no default_factory
        if field.default == field.default_factory == field.default.__class__.__name__:
            required.append(field.name)
        # Better check: use MISSING sentinel
        from dataclasses import MISSING

        if field.default is MISSING and field.default_factory is MISSING:
            required.append(field.name)

    return {"type": "object", "properties": properties, "required": required}


def _get_annotated_class_schema(class_type: type) -> dict[str, Any]:
    """Generate schema for regular classes with type annotations."""
    properties = {}
    required = []

    for name, field_type in class_type.__annotations__.items():
        properties[name] = get_type_schema(field_type)

        # Check if the class has an __init__ method and inspect its signature
        try:
            sig = inspect.signature(class_type)
            param = sig.parameters.get(name)
            if param and param.default == inspect.Parameter.empty:
                required.append(name)
        except (ValueError, TypeError):
            # If we can't get signature, assume all fields are required
            required.append(name)

    return {"type": "object", "properties": properties, "required": required}
