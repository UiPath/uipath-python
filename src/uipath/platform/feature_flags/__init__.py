"""UiPath Feature Flags.

Local-only feature flag registry for the UiPath SDK.
"""

from .feature_flags import configure, get, is_enabled, reset

__all__ = [
    "configure",
    "get",
    "is_enabled",
    "reset",
]
