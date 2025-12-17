"""Sanitization utilities for names and identifiers."""

import re


def sanitize_string(name: str) -> str:
    """Sanitize a string for LLM compatibility.

    Used for sanitizing names like tool names, node names, or other identifiers
    to make them compatible with LLMs. Ensures the string contains only
    alphanumeric characters, underscores, and hyphens, with a maximum length
    of 64 characters.

    Args:
        name: The original string to sanitize.

    Returns:
        Sanitized string safe for LLM usage.

    Examples:
        >>> sanitize_string("My Tool Name")
        'My_Tool_Name'
        >>> sanitize_string("tool@special!chars")
        'toolspecialchars'
    """
    trim_whitespaces = "_".join(name.split())
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", trim_whitespaces)
    return sanitized[:64]
