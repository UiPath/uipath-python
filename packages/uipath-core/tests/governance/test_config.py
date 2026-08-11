"""Tests for the governance feature-flag gate."""

from __future__ import annotations

import pytest

from uipath.core.feature_flags import FeatureFlags
from uipath.core.governance.config import (
    GOVERNANCE_FEATURE_FLAG,
    is_governance_enabled,
)


@pytest.fixture(autouse=True)
def _reset_flags():
    """Each test starts and ends with a clean flags registry."""
    FeatureFlags.reset_flags()
    yield
    FeatureFlags.reset_flags()


def test_governance_flag_name_is_stable():
    """The flag name is a public contract shared with the runtime layer."""
    assert GOVERNANCE_FEATURE_FLAG == "EnablePythonGovernanceChecker"


def test_is_governance_enabled_defaults_to_false():
    """With nothing configured, the gate defaults to disabled.

    The platform / host runtime must explicitly opt into governance
    (programmatically via :class:`FeatureFlags`, via gitops, or via the
    ``UIPATH_FEATURE_EnablePythonGovernanceChecker`` env var). This
    keeps the SDK safe-by-default for callers that haven't yet
    integrated with the governance backend.
    """
    assert is_governance_enabled() is False


def test_is_governance_enabled_respects_programmatic_disable():
    """Programmatic ``False`` flips the gate off."""
    FeatureFlags.configure_flags({GOVERNANCE_FEATURE_FLAG: False})
    assert is_governance_enabled() is False


def test_is_governance_enabled_respects_programmatic_enable():
    """Programmatic ``True`` keeps the gate on."""
    FeatureFlags.configure_flags({GOVERNANCE_FEATURE_FLAG: True})
    assert is_governance_enabled() is True


def test_is_governance_enabled_reads_env_var_fallback(monkeypatch):
    """When nothing is configured programmatically, the env-var fallback wins."""
    monkeypatch.setenv(f"UIPATH_FEATURE_{GOVERNANCE_FEATURE_FLAG}", "false")
    assert is_governance_enabled() is False
