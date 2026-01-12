"""Text token utilities for building prompts from tokenized content."""

import json
from typing import Any

from uipath.agent.models.agent import TextToken, TextTokenType


def build_string_from_tokens(
    tokens: list[TextToken],
    input_arguments: dict[str, Any],
    tool_names: list[str] | None = None,
    escalation_names: list[str] | None = None,
    context_names: list[str] | None = None,
) -> str:
    """Build a string from text tokens with variable replacement.

    Args:
        tokens: List of text tokens to join
        input_arguments: Dictionary of input arguments for variable replacement
        tool_names: Optional list of tool names for tool.* variable resolution
        escalation_names: Optional list of escalation names for escalation.* variable resolution
        context_names: Optional list of context names for context.* variable resolution
    """
    parts: list[str] = []

    for token in tokens:
        if token.type == TextTokenType.SIMPLE_TEXT:
            parts.append(token.raw_string)
        elif token.type == TextTokenType.EXPRESSION:
            parts.append(token.raw_string)
        elif token.type == TextTokenType.VARIABLE:
            resolved_value = _process_variable_token(
                token.raw_string,
                input_arguments,
                tool_names,
                escalation_names,
                context_names,
            )
            parts.append(resolved_value)
        else:
            parts.append(token.raw_string)

    return "".join(parts)


def _process_variable_token(
    raw_string: str,
    input_arguments: dict[str, Any],
    tool_names: list[str] | None = None,
    escalation_names: list[str] | None = None,
    context_names: list[str] | None = None,
) -> str:
    """Process a variable token and return its resolved value.

    Returns:
        The resolved variable value or original string if unresolved
    """
    if not raw_string or not raw_string.strip():
        return raw_string

    if raw_string.lower() == "input":
        return json.dumps(input_arguments, ensure_ascii=False)

    dot_index = raw_string.find(".")
    if dot_index < 0:
        return raw_string

    prefix = raw_string[:dot_index].lower()
    path = raw_string[dot_index + 1 :]

    if prefix == "input":
        value = safe_get_nested(input_arguments, path)
        return serialize_argument(value) if value is not None else raw_string
    elif prefix == "output":
        return path
    elif prefix == "tools":
        found_name = _find_resource_name(path, tool_names)
        return found_name if found_name else raw_string
    elif prefix == "escalations":
        found_name = _find_resource_name(path, escalation_names)
        return found_name if found_name else raw_string
    elif prefix == "contexts":
        found_name = _find_resource_name(path, context_names)
        return found_name if found_name else raw_string

    return raw_string


def _find_resource_name(name: str, resource_names: list[str] | None) -> str | None:
    """Find a resource name in the list.

    Args:
        name: The name to search for
        resource_names: List of resource names to search in

    Returns:
        The matching resource name, or None if not found
    """
    if not resource_names:
        return None

    name_lower = name.lower()
    return next(
        (
            resource_name
            for resource_name in resource_names
            if resource_name.lower() == name_lower
        ),
        None,
    )


def safe_get_nested(data: dict[str, Any], path: str) -> Any:
    """Get nested dictionary value using dot notation (e.g., "user.email")."""
    keys = path.split(".")
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None

    return current


def serialize_argument(
    value: str | int | float | bool | list[Any] | dict[str, Any] | None,
) -> str:
    """Serialize value for interpolation: primitives as-is, collections as JSON."""
    if value is None:
        return ""
    if isinstance(value, (list, dict, bool)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
