"""Type conversion utilities for runtime input/output handling."""

import inspect
from dataclasses import asdict, is_dataclass
from typing import Any, Type, TypeVar, cast, get_type_hints

from pydantic import BaseModel

T = TypeVar("T")


def is_pydantic_model(cls: Type[Any]) -> bool:
    """Check if a class is a Pydantic model."""
    try:
        return inspect.isclass(cls) and issubclass(cls, BaseModel)
    except TypeError:
        return False


def convert_to_class(data: dict[str, Any], cls: Type[T]) -> T:
    """Convert a dictionary to a class instance (Pydantic, dataclass, or regular)."""
    # Pydantic models
    if is_pydantic_model(cls):
        pydantic_cls = cast(Type[BaseModel], cls)
        return cast(T, pydantic_cls.model_validate(data))

    # Dataclasses
    if is_dataclass(cls):
        return _convert_to_dataclass(data, cls)

    # Regular classes
    return _convert_to_regular_class(data, cls)


def _convert_to_dataclass(data: dict[str, Any], cls: Type[T]) -> T:
    """Convert dictionary to dataclass instance."""
    field_types = get_type_hints(cls)
    converted_data = {}

    for field_name, field_type in field_types.items():
        if field_name not in data:
            continue

        value = data[field_name]
        # Recursively convert nested structures
        if isinstance(value, dict) and _is_nested_type(field_type):
            value = convert_to_class(value, cast(Type[Any], field_type))

        converted_data[field_name] = value

    return cls(**converted_data)


def _convert_to_regular_class(data: dict[str, Any], cls: Type[T]) -> T:
    """Convert dictionary to regular class instance."""
    sig = inspect.signature(cls.__init__)
    init_args = {}

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        if param_name in data:
            value = data[param_name]
            param_type = (
                param.annotation if param.annotation != inspect.Parameter.empty else Any
            )

            # Recursively convert nested structures
            if isinstance(value, dict) and _is_nested_type(param_type):
                value = convert_to_class(value, cast(Type[Any], param_type))

            init_args[param_name] = value
        elif param.default != inspect.Parameter.empty:
            init_args[param_name] = param.default

    return cls(**init_args)


def convert_from_class(obj: Any) -> dict[str, Any]:
    """Convert a class instance to a dictionary."""
    if obj is None:
        return {}

    # Handle primitives and built-in types first
    if isinstance(obj, (str, int, float, bool, list, tuple)):
        return {"result": obj}

    # Handle dict - return as-is
    if isinstance(obj, dict):
        return obj

    # Pydantic models
    if isinstance(obj, BaseModel):
        return obj.model_dump()

    # Dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)

    # Regular classes with __dict__
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return _convert_from_regular_class(obj)

    # Fallback
    return {}


def _convert_from_regular_class(obj: Any) -> dict[str, Any]:
    """Convert regular class instance to dictionary."""
    result = {}
    for key, value in obj.__dict__.items():
        if not key.startswith("_"):
            # Recursively convert nested objects
            if (
                isinstance(value, BaseModel)
                or is_dataclass(value)
                or (
                    hasattr(value, "__dict__")
                    and not isinstance(value, (dict, list, str, int, float, bool))
                )
            ):
                result[key] = convert_from_class(value)
            else:
                result[key] = value
    return result


def _is_nested_type(type_hint: Type[Any]) -> bool:
    """Check if a type is a nested structure that needs conversion."""
    return (
        is_dataclass(type_hint)
        or is_pydantic_model(type_hint)
        or (inspect.isclass(type_hint) and hasattr(type_hint, "__annotations__"))
    )
