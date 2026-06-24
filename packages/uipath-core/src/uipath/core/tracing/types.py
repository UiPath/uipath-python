"""Tracing types for UiPath SDK."""

from typing import Callable

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, Field

from uipath.core.feature_flags import FeatureFlags

# Instrumentation scopes whose spans are third-party internal noise and should
# not be exported to LLM Observability. The a2a-sdk auto-instruments its
# JSON-RPC transport under the "a2a-python-sdk" scope (one span per transport
# method), which surfaces as unparented, low-value nodes in the execution trace;
# meaningful A2A activity is emitted as the caller's own span instead. Dropped at
# the span-processor layer so the exclusion applies to every agent (coded and
# low-code), independent of any optional UiPathTraceSettings.span_filter.
EXCLUDED_INSTRUMENTATION_SCOPES: frozenset[str] = frozenset({"a2a-python-sdk"})

# Feature flag gating the exclusion. Ships default-off (set
# ``UIPATH_FEATURE_ExcludeThirdPartyTraceScopes=true`` to opt in); the default is
# flipped on in a later release once the noise filtering is validated in the field.
EXCLUDE_SCOPES_FEATURE_FLAG = "ExcludeThirdPartyTraceScopes"


def is_excluded_instrumentation_scope(span: ReadableSpan) -> bool:
    """Return True when the span comes from an excluded instrumentation scope.

    Gated behind the ``UIPATH_FEATURE_ExcludeThirdPartyTraceScopes`` feature flag
    (default off). Used by the UiPath span processors to drop third-party
    instrumentation noise (see ``EXCLUDED_INSTRUMENTATION_SCOPES``) before export,
    independent of any configured ``span_filter``.
    """
    if not FeatureFlags.is_flag_enabled(EXCLUDE_SCOPES_FEATURE_FLAG):
        return False
    scope = getattr(span, "instrumentation_scope", None)
    return scope is not None and scope.name in EXCLUDED_INSTRUMENTATION_SCOPES


class UiPathTraceSettings(BaseModel):
    """Trace settings for UiPath SDK."""

    model_config = {"arbitrary_types_allowed": True}  # Needed for Callable

    span_filter: Callable[[ReadableSpan], bool] | None = Field(
        default=None,
        description=(
            "Optional filter to decide whether a span should be exported. "
            "Called when a span ends with a ReadableSpan argument. "
            "Return True to export, False to skip."
        ),
    )
