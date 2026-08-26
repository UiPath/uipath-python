"""UiPath Feature Flags.

Local-only feature flag registry for the UiPath SDK.
"""

from .feature_flags import (
    DEEP_RAG_FROM_ATTACHMENTS_FEATURE_FLAG,
    JIT_ESCALATION_APPS_FEATURE_FLAG,
    FeatureFlags,
    FeatureFlagsManager,
)

__all__ = [
    "DEEP_RAG_FROM_ATTACHMENTS_FEATURE_FLAG",
    "JIT_ESCALATION_APPS_FEATURE_FLAG",
    "FeatureFlags",
    "FeatureFlagsManager",
]
