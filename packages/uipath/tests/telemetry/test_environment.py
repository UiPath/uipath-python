"""Tests for resolving the UiPath environment from the configured base URL."""

import pytest

from uipath.platform.constants import ENV_BASE_URL
from uipath.telemetry._environment import (
    environment_from_base_url,
    resolve_environment,
)


class TestEnvironmentFromBaseUrl:
    @pytest.mark.parametrize(
        "base_url, expected",
        [
            ("https://alpha.uipath.com/myOrg/myTenant", "alpha"),
            ("https://staging.uipath.com/myOrg/myTenant", "staging"),
            ("https://cloud.uipath.com/myOrg/myTenant", "cloud"),
        ],
    )
    def test_known_hosts_resolve_to_their_environment(self, base_url, expected):
        assert environment_from_base_url(base_url) == expected

    def test_subdomain_is_not_a_recognised_host(self):
        assert environment_from_base_url("https://tenant.alpha.uipath.com/o") == "cloud"

    def test_host_matching_is_case_insensitive(self):
        assert environment_from_base_url("https://ALPHA.UiPath.COM/o") == "alpha"

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://alpha.uipath.com.evil.com/o",
            "https://alpha.uipath.com_evil.com/o",
        ],
    )
    def test_lookalike_suffix_does_not_match(self, base_url):
        assert environment_from_base_url(base_url) == "cloud"

    def test_prefixed_hostname_does_not_match(self):
        assert environment_from_base_url("https://notalpha.uipath.com/o") == "cloud"

    @pytest.mark.parametrize(
        "base_url",
        [
            None,
            "https://automationsuite.mycorp.example.com/o",
            "alpha.uipath.com/myOrg/myTenant",
            "not a url at all",
        ],
    )
    def test_unresolvable_base_url_falls_back_to_cloud(self, base_url):
        assert environment_from_base_url(base_url) == "cloud"


class TestResolveEnvironment:
    def test_reads_base_url_from_environment(self, monkeypatch):
        monkeypatch.setenv(ENV_BASE_URL, "https://alpha.uipath.com/myOrg/myTenant")

        assert resolve_environment() == "alpha"

    def test_unauthenticated_falls_back_to_cloud(self, monkeypatch):
        monkeypatch.delenv(ENV_BASE_URL, raising=False)

        assert resolve_environment() == "cloud"
