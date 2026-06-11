"""Utility for resolving dot-notation paths from agent output dictionaries.

Supports:
- "*" → return entire output (default behavior)
- "result" → flat key lookup (backward compatible)
- "result.calculation.value" → nested dot-notation path
- "items[0].name" → array index access with dot-notation
- "items[2].details.score" → mixed nested object and array access

Examples:
    >>> resolve_output_path({"result": {"value": 42}}, "result.value")
    42
    >>> resolve_output_path({"items": [{"name": "a"}, {"name": "b"}]}, "items[1].name")
    'b'
    >>> resolve_output_path({"result": 5}, "*")
    {"result": 5}
"""

import re
from typing import Any


def resolve_output_path(output: Any, path: str) -> Any:
    """Resolve a dot-notation path with optional array indexing from output.

    Args:
        output: The output dictionary (or any value) to resolve the path from.
        path: The path string. "*" returns the full output.
              Dot notation for nested objects: "a.b.c"
              Bracket notation for array indices: "items[0].name"

    Returns:
        The resolved value at the given path.

    Raises:
        KeyError: If a dict key in the path is not found.
        IndexError: If an array index is out of range.
        TypeError: If the path tries to index into a non-dict/non-list value.
    """
    if path == "*":
        return output

    tokens = _tokenize_path(path)
    current = output

    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, (list, tuple)):
                raise TypeError(
                    f"Cannot index into {type(current).__name__} with integer index [{token}]"
                )
            current = current[token]
        else:
            if not isinstance(current, dict):
                raise TypeError(
                    f"Cannot access key '{token}' on {type(current).__name__}"
                )
            current = current[token]

    return current


# Pattern to match either:
#   - a bare key segment (no dots or brackets)
#   - a bracket index like [0], [12]
_TOKEN_PATTERN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _tokenize_path(path: str) -> list[str | int]:
    """Parse a path string into a list of string keys and integer indices.

    Examples:
        "result" → ["result"]
        "result.value" → ["result", "value"]
        "items[0].name" → ["items", 0, "name"]
        "data[2].nested.list[0]" → ["data", 2, "nested", "list", 0]
    """
    tokens: list[str | int] = []
    for match in _TOKEN_PATTERN.finditer(path):
        key_part, index_part = match.groups()
        if index_part is not None:
            tokens.append(int(index_part))
        else:
            tokens.append(key_part)

    if not tokens:
        raise ValueError(f"Invalid path: '{path}'")

    return tokens
