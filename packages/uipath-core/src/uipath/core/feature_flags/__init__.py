"""UiPath Feature Flags.

Local-only feature flag registry for the UiPath SDK.
"""

from .feature_flags import (
    JIT_ESCALATION_APPS_FEATURE_FLAG,
    FeatureFlags,
    FeatureFlagsManager,
)

__all__ = [
    "JIT_ESCALATION_APPS_FEATURE_FLAG",
    "FeatureFlags",
    "FeatureFlagsManager",
]
