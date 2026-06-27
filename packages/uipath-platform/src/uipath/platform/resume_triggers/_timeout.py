"""Helpers for interrupt timeout resume values."""

import json
from collections.abc import Mapping
from typing import Any, TypeVar

UIPATH_METADATA_KEY = "__uipath"
UIPATH_TIMEOUT_KIND = "timeout"

T = TypeVar("T")


class UiPathTimeoutError(TimeoutError):
    """Raised when an interrupt resumes because its timeout trigger fired."""

    def __init__(self, timeout: Mapping[str, Any]) -> None:
        self.metadata = dict(timeout)
        self.timeout = self.metadata.get("timeout")
        message = "UiPath interrupt timed out"
        if self.timeout is not None:
            message = f"{message} after {self.timeout} seconds"
        super().__init__(message)


def _coerce_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, Mapping):
            return parsed
    return None


def get_timeout(value: Any) -> dict[str, Any] | None:
    """Return timeout metadata from a resume value, if it is a timeout."""
    payload = _coerce_mapping(value)
    if payload is None:
        return None

    metadata = payload.get(UIPATH_METADATA_KEY)
    if not isinstance(metadata, Mapping):
        return None
    if metadata.get("kind") != UIPATH_TIMEOUT_KIND:
        return None
    return dict(metadata)


def check_timeout(value: Any) -> dict[str, Any] | None:
    """Alias for get_timeout."""
    return get_timeout(value)


def is_timeout(value: Any) -> bool:
    """Return whether a resume value represents a timeout."""
    return get_timeout(value) is not None


def assert_no_timeout(value: T) -> T:
    """Return value unless it represents a timeout, then raise UiPathTimeoutError."""
    timeout = get_timeout(value)
    if timeout is not None:
        raise UiPathTimeoutError(timeout)
    return value
