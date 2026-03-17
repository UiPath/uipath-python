"""Shared helpers for error payload extractors."""

from typing import Any, TypeVar
from urllib.parse import urlparse

T = TypeVar("T")


def get_field(body: dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value found for the given keys.

    Automatically tries both camelCase and PascalCase for each key.
    """
    for key in keys:
        val = body.get(key)
        if val is not None:
            return val
        val = body.get(key[0].swapcase() + key[1:])
        if val is not None:
            return val
    return None


def get_typed_field(body: dict[str, Any], type_: type[T], *keys: str) -> T | None:
    """Return the first non-None value matching *type_* for the given keys.

    Skips values that don't match the expected type.
    """
    val = get_field(body, *keys)
    if val is None or not isinstance(val, type_):
        return None
    return val


def get_str_field(body: dict[str, Any], *keys: str) -> str | None:
    """Return the first non-None value for the given keys, converted to str."""
    val = get_field(body, *keys)
    if val is None:
        return None
    return str(val)


def extract_service_prefix(url: str) -> str | None:
    """Extract the service prefix (e.g. 'orchestrator_') from a UiPath URL path."""
    path = urlparse(url).path if "://" in url else url
    for segment in path.strip("/").split("/"):
        if segment.endswith("_") and len(segment) > 1:
            return segment
    return None


def is_llm_path(url: str) -> bool:
    """Check if the URL targets the LLM Gateway."""
    return "/llm/" in url
