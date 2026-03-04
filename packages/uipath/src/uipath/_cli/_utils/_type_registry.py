"""Type registry for safe parameter type resolution.

This module provides a safe way to resolve type strings to Python types,
replacing the use of eval() which is a security vulnerability.

The TYPE_REGISTRY is used by the ServiceMetadata system to convert type
strings (e.g., "str", "int") to actual Python types for Click parameter
validation.

Security Note:
    This registry approach prevents arbitrary code execution that would be
    possible with eval(). Only explicitly registered types can be used.

Example:
    >>> from ._type_registry import get_type
    >>> str_type = get_type("str")
    >>> str_type is str
    True
    >>> get_type("InvalidType")  # Raises ValueError
    ValueError: Unknown type: 'InvalidType'. Valid types: bool, float, int, str
"""

from typing import Any, Type

TYPE_REGISTRY: dict[str, Type[Any]] = {
    "str": str,
    "int": int,
    "bool": bool,
    "float": float,
}


def get_type(type_name: str) -> Type[Any]:
    """Get Python type from string name safely.

    Args:
        type_name: String name of the type (e.g., "str", "int", "bool", "float")

    Returns:
        The Python type corresponding to the type name

    Raises:
        ValueError: If type_name is not in the registry

    Example:
        >>> get_type("str")
        <class 'str'>
        >>> get_type("int")
        <class 'int'>
        >>> get_type("InvalidType")
        Traceback (most recent call last):
        ...
        ValueError: Unknown type: 'InvalidType'. Valid types: bool, float, int, str
    """
    param_type = TYPE_REGISTRY.get(type_name)
    if param_type is None:
        valid_types = ", ".join(sorted(TYPE_REGISTRY.keys()))
        raise ValueError(f"Unknown type: '{type_name}'. Valid types: {valid_types}")
    return param_type


def register_type(type_name: str, type_class: Type[Any]) -> None:
    """Register a new type in the registry.

    This function allows extending the registry with custom types if needed.
    Use with caution and only register types that are safe for CLI parameters.

    Args:
        type_name: String name for the type
        type_class: The Python type class

    Raises:
        ValueError: If type_name already exists in registry

    Example:
        >>> from pathlib import Path
        >>> register_type("path", Path)
        >>> get_type("path")
        <class 'pathlib.Path'>
    """
    if type_name in TYPE_REGISTRY:
        raise ValueError(
            f"Type '{type_name}' is already registered as {TYPE_REGISTRY[type_name]}"
        )
    TYPE_REGISTRY[type_name] = type_class


def is_valid_type(type_name: str) -> bool:
    """Check if a type name is registered.

    Args:
        type_name: String name to check

    Returns:
        True if type is registered, False otherwise

    Example:
        >>> is_valid_type("str")
        True
        >>> is_valid_type("InvalidType")
        False
    """
    return type_name in TYPE_REGISTRY


__all__ = ["TYPE_REGISTRY", "get_type", "register_type", "is_valid_type"]
