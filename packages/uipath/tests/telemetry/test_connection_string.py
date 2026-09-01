"""Tests for per-environment Application Insights connection string resolution."""

from unittest.mock import patch

import pytest

from uipath.platform.constants import ENV_BASE_URL
from uipath.telemetry._track import _get_connection_string

ALPHA_URL = "https://alpha.uipath.com/myOrg/myTenant"
STAGING_URL = "https://staging.uipath.com/myOrg/myTenant"
CLOUD_URL = "https://cloud.uipath.com/myOrg/myTenant"

_TELEMETRY_ENV_VARS = (
    "TELEMETRY_CONNECTION_STRING",
    "TELEMETRY_CONNECTION_STRING_ALPHA",
    "TELEMETRY_CONNECTION_STRING_STAGING",
    "TELEMETRY_CONNECTION_STRING_PROD",
)


@pytest.fixture(autouse=True)
def clear_telemetry_env(monkeypatch):
    for name in (*_TELEMETRY_ENV_VARS, ENV_BASE_URL):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def unsubstituted_constants():
    """Default every baked constant to its unsubstituted placeholder."""
    with (
        patch(
            "uipath.telemetry._track._CONNECTION_STRING_ALPHA",
            "$CONNECTION_STRING_ALPHA",
        ),
        patch(
            "uipath.telemetry._track._CONNECTION_STRING_STAGING",
            "$CONNECTION_STRING_STAGING",
        ),
        patch(
            "uipath.telemetry._track._CONNECTION_STRING_PROD",
            "$CONNECTION_STRING_PROD",
        ),
    ):
        yield


class TestEnvironmentRouting:
    @patch("uipath.telemetry._track._CONNECTION_STRING_ALPHA", "baked-alpha")
    @patch("uipath.telemetry._track._CONNECTION_STRING_STAGING", "baked-staging")
    @patch("uipath.telemetry._track._CONNECTION_STRING_PROD", "baked-prod")
    @pytest.mark.parametrize(
        "base_url, expected",
        [
            (ALPHA_URL, "baked-alpha"),
            (STAGING_URL, "baked-staging"),
            (CLOUD_URL, "baked-prod"),
        ],
    )
    def test_authenticated_run_uses_its_environment(
        self, monkeypatch, base_url, expected
    ):
        monkeypatch.setenv(ENV_BASE_URL, base_url)

        assert _get_connection_string() == expected

    @patch("uipath.telemetry._track._CONNECTION_STRING_ALPHA", "baked-alpha")
    @patch("uipath.telemetry._track._CONNECTION_STRING_PROD", "baked-prod")
    def test_unauthenticated_run_uses_prod(self):
        assert _get_connection_string() == "baked-prod"

    @patch("uipath.telemetry._track._CONNECTION_STRING_ALPHA", "baked-alpha")
    @patch("uipath.telemetry._track._CONNECTION_STRING_PROD", "baked-prod")
    def test_unrecognized_host_uses_prod(self, monkeypatch):
        monkeypatch.setenv(ENV_BASE_URL, "https://automationsuite.mycorp.example.com")

        assert _get_connection_string() == "baked-prod"


class TestOverridePrecedence:
    @patch("uipath.telemetry._track._CONNECTION_STRING_ALPHA", "baked-alpha")
    def test_bare_override_wins_over_environment_routing(self, monkeypatch):
        monkeypatch.setenv(ENV_BASE_URL, ALPHA_URL)
        monkeypatch.setenv("TELEMETRY_CONNECTION_STRING", "explicit")
        monkeypatch.setenv("TELEMETRY_CONNECTION_STRING_ALPHA", "env-alpha")

        assert _get_connection_string() == "explicit"

    @patch("uipath.telemetry._track._CONNECTION_STRING_ALPHA", "baked-alpha")
    def test_per_environment_override_beats_baked_constant(self, monkeypatch):
        monkeypatch.setenv(ENV_BASE_URL, ALPHA_URL)
        monkeypatch.setenv("TELEMETRY_CONNECTION_STRING_ALPHA", "env-alpha")

        assert _get_connection_string() == "env-alpha"

    @patch("uipath.telemetry._track._CONNECTION_STRING_ALPHA", "baked-alpha")
    def test_override_for_another_environment_is_ignored(self, monkeypatch):
        monkeypatch.setenv(ENV_BASE_URL, ALPHA_URL)
        monkeypatch.setenv("TELEMETRY_CONNECTION_STRING_STAGING", "env-staging")

        assert _get_connection_string() == "baked-alpha"


class TestUnconfiguredEnvironment:
    """A slot the build never populated reports nowhere, not elsewhere."""

    @patch("uipath.telemetry._track._CONNECTION_STRING_PROD", "baked-prod")
    def test_unsubstituted_slot_does_not_fall_through(self, monkeypatch):
        monkeypatch.setenv(ENV_BASE_URL, ALPHA_URL)

        assert _get_connection_string() is None

    @patch("uipath.telemetry._track._CONNECTION_STRING_ALPHA", "")
    @patch("uipath.telemetry._track._CONNECTION_STRING_PROD", "baked-prod")
    def test_blank_slot_from_a_missing_secret_does_not_fall_through(self, monkeypatch):
        monkeypatch.setenv(ENV_BASE_URL, ALPHA_URL)

        assert _get_connection_string() is None
