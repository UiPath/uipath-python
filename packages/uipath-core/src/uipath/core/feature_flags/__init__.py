"""UiPath Feature Flags.

Local-only feature flag registry for the UiPath SDK.
"""

from .feature_flags import FeatureFlags, FeatureFlagsManager

__all__ = [
    "FeatureFlags",
    "FeatureFlagsManager",
]
