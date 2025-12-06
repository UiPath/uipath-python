"""UiPath resume trigger enums."""

from enum import Enum


class PropertyName(str, Enum):
    """UiPath trigger property names."""

    INTERNAL = "__internal"


class TriggerMarker(str, Enum):
    """UiPath trigger markers.

    These markers are used as properties of resume triggers objects for special handling at runtime.
    """

    NO_CONTENT = "NO_CONTENT"
