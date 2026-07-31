"""Helpers for resume values produced by timeout triggers."""

from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import ValidationError
from uipath.core.triggers import (
    UIPATH_METADATA_KEY,
    UiPathResumeMetadata,
    UiPathResumeTriggerType,
)

T = TypeVar("T")


class UiPathTimeoutError(TimeoutError):
    """Raised when a resume value came from a UiPath timeout trigger."""

    def __init__(self, value: Any):
        """Create a timeout error that keeps the original resume value."""
        super().__init__("UiPath interrupt timed out.")
        self.value = value


def is_timeout(value: Any) -> bool:
    """Return True when a resume value came from a UiPath timeout trigger."""
    metadata = get_resume_metadata(value)
    return (
        metadata is not None and metadata.trigger_type == UiPathResumeTriggerType.TIMER
    )


def assert_no_timeout(value: T) -> T:
    """Raise UiPathTimeoutError if a resume value came from a timeout trigger."""
    if is_timeout(value):
        raise UiPathTimeoutError(value)
    return value


def get_resume_metadata(value: Any) -> UiPathResumeMetadata | None:
    """Return UiPath resume metadata when present on a resume value."""
    metadata = _metadata(value)
    if metadata is None:
        return None

    try:
        return UiPathResumeMetadata.model_validate(metadata)
    except ValidationError:
        return None


def _metadata(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    metadata = value.get(UIPATH_METADATA_KEY)
    return metadata if isinstance(metadata, Mapping) else None
