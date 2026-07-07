"""Governance configuration.

Process-level feature-flag gate that lets direct callers (agents
constructing an evaluator themselves) decide whether to wire up
governance. The :class:`uipath.core.governance.EnforcementMode` value
type is defined in :mod:`uipath.core.governance.models`; the per-policy
runtime state that selects a mode (backend-supplied via the
``/runtime/policy`` client) lives outside this package.
"""

from __future__ import annotations

import warnings

from uipath.core.feature_flags import FeatureFlags

# Feature flag name controlling whether governance runs.
# A single shared gate so the host-driven injection path and direct
# callers (agents constructing an evaluator themselves) honour the
# same toggle.
GOVERNANCE_FEATURE_FLAG = "EnablePythonGovernanceChecker"


def is_governance_enabled() -> bool:
    """Return whether the ``EnablePythonGovernanceChecker`` flag is enabled.

    .. deprecated::
        The CLI ``run`` / ``debug`` bootstrap no longer consults this
        gate — it always fetches policy and lets the backend-supplied
        enforcement mode decide. This helper remains only for direct
        callers (agents constructing an evaluator themselves) that gate
        their own wiring on the flag, and will be removed in a future
        major release.

    Governance is **off by default** — the flag must be explicitly set
    to ``true`` (programmatically via the ``FeatureFlags`` registry, or
    via the ``UIPATH_FEATURE_EnablePythonGovernanceChecker`` env var)
    for this function to return ``True``.

    Resolution order:

    1. :meth:`uipath.core.feature_flags.FeatureFlagsManager.is_flag_enabled` -
       the in-process programmatic registry (typically populated from
       gitops) and its own ``UIPATH_FEATURE_<name>`` env-var fallback.
    2. Default ``False`` (governance disabled).
    """
    warnings.warn(
        "is_governance_enabled() is deprecated;"
        "It will be removed in a future major release.",
        DeprecationWarning,
        stacklevel=2,
    )
    return FeatureFlags.is_flag_enabled(GOVERNANCE_FEATURE_FLAG, default=False)
