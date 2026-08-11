"""Governance configuration.

Process-level feature-flag gate that decides whether the Python
governance checker runs at all. The
:class:`uipath.core.governance.EnforcementMode` value type is defined
in :mod:`uipath.core.governance.models`; the per-policy runtime state
that selects a mode (backend-supplied via the ``/runtime/policy``
client) lives outside this package.
"""

from __future__ import annotations

from uipath.core.feature_flags import FeatureFlags

# Feature flag name controlling whether governance runs.
# A single shared gate so the host-driven injection path and direct
# callers (agents constructing an evaluator themselves) honour the
# same toggle.
GOVERNANCE_FEATURE_FLAG = "EnablePythonGovernanceChecker"


def is_governance_enabled() -> bool:
    """Return whether the ``EnablePythonGovernanceChecker`` flag is enabled.

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
    return FeatureFlags.is_flag_enabled(GOVERNANCE_FEATURE_FLAG, default=False)
