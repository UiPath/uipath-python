"""Utility functions for legacy evaluators."""

import json
from typing import Any, Optional

from ..._utils.constants import COMMUNITY_agents_SUFFIX


def clean_model_name(model: str) -> str:
    """Remove community-agents suffix from model name.

    Args:
        model: Model name that may have the community suffix

    Returns:
        Model name without the community suffix
    """
    if model.endswith(COMMUNITY_agents_SUFFIX):
        return model.replace(COMMUNITY_agents_SUFFIX, "")
    return model


def serialize_object(
    content: Any,
    sort_keys: bool = False,
) -> str:
    """Serialize content to string format.

    Args:
        content: Content to serialize (str, dict, list, etc.)
        sort_keys: Whether to sort dict keys (default: False)

    Returns:
        Serialized string representation
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        if sort_keys:
            content = dict(sorted(content.items()))
        return json.dumps(content, default=str, separators=(",", ":"))
    else:
        return json.dumps(content, default=str, separators=(",", ":"))


def safe_get_span_attributes(span: Any) -> Optional[dict[str, Any]]:
    """Safely extract attributes from a span.

    Args:
        span: The span object

    Returns:
        Span attributes dict, or None if not available
    """
    if not hasattr(span, "attributes") or span.attributes is None:
        return None
    return span.attributes


def parse_json_value(value: str) -> Any:
    """Safely parse a JSON string value.

    Args:
        value: JSON string to parse

    Returns:
        Parsed JSON object

    Raises:
        ValueError: If string cannot be parsed as JSON
    """
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise ValueError(f"Cannot parse JSON value: {value}") from e
