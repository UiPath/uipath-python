"""
Unit tests for OidcUtils.get_auth_config() method.

IMPORTANT: Backwards Compatibility Notice
=========================================
If any values in auth_config.json are changed, we MUST maintain backwards
compatibility with release/2025.10 branches or later.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from uipath._cli._auth._oidc_utils import (
    OidcUtils,
    _get_version_from_api,
    _is_cloud_domain,
    _select_config_file,
)


class TestOidcUtils:
    """Test suite for OidcUtils class."""

    def test_auth_config_backwards_compatibility_v2025_10(self):
        """
        Test that auth_config_25_10.json maintains backwards compatibility with release/v2025.10.

        This test validates that the authentication configuration values remain
        unchanged to ensure compatibility with release/v2025.10 and later branches.

        CRITICAL: Any failure indicates a breaking change that requires coordination
        across all supported release branches.
        """
        # Read the actual auth_config_25_10.json file
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "src",
            "uipath",
            "_cli",
            "_auth",
            "auth_config_25_10.json",
        )

        with open(config_path, "r") as f:
            actual_config = json.load(f)

        # Assert exact values for non-scope fields
        assert actual_config["client_id"] == "36dea5b8-e8bb-423d-8e7b-c808df8f1c00", (
            f"BACKWARDS COMPATIBILITY VIOLATION: client_id has changed! "
            f"Expected: 36dea5b8-e8bb-423d-8e7b-c808df8f1c00, Got: {actual_config['client_id']}"
        )

        assert (
            actual_config["redirect_uri"]
            == "http://localhost:__PY_REPLACE_PORT__/oidc/login"
        ), (
            f"BACKWARDS COMPATIBILITY VIOLATION: redirect_uri has changed! "
            f"Expected: http://localhost:__PY_REPLACE_PORT__/oidc/login, Got: {actual_config['redirect_uri']}"
        )

        assert actual_config["port"] == 8104, (
            f"BACKWARDS COMPATIBILITY VIOLATION: port has changed! "
            f"Expected: 8104, Got: {actual_config['port']}"
        )

        # For scopes, ensure actual scopes are a subset of the allowed scopes (no new scopes allowed)
        allowed_scopes = set(
            [
                "offline_access",
                "ProcessMining",
                "OrchestratorApiUserAccess",
                "StudioWebBackend",
                "IdentityServerApi",
                "ConnectionService",
                "DataService",
                "DocumentUnderstanding",
                "Du.Digitization.Api",
                "Du.Classification.Api",
                "Du.Extraction.Api",
                "Du.Validation.Api",
                "EnterpriseContextService",
                "Directory",
                "JamJamApi",
                "LLMGateway",
                "LLMOps",
                "OMS",
                "RCS.FolderAuthorization",
                "TM.Projects",
                "TM.TestCases",
                "TM.Requirements",
                "TM.TestSets",
            ]
        )

        actual_scopes = set(actual_config["scope"].split())

        assert actual_scopes.issubset(allowed_scopes), (
            f"BACKWARDS COMPATIBILITY VIOLATION: New scopes detected that are not allowed on v2025.10! "
            f"New scopes: {actual_scopes - allowed_scopes}. "
            f"Only subsets of the following scopes are permitted: {sorted(allowed_scopes)}"
        )

    @pytest.mark.parametrize(
        "domain,expected",
        [
            ("https://alpha.uipath.com", True),
            ("https://staging.uipath.com", True),
            ("https://cloud.uipath.com", True),
            ("https://ALPHA.UIPATH.COM", True),  # Test case insensitivity
            ("https://custom.domain.com", False),
            ("https://cloud.uipath.dev", False),
            ("https://alpha-test.uipath.com", False),
        ],
    )
    def test_is_cloud_domain(self, domain, expected):
        """Test _is_cloud_domain correctly identifies cloud domains."""
        assert _is_cloud_domain(domain) == expected

    def test_get_version_from_api_success(self):
        """Test _get_version_from_api successfully fetches version."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "version": "25.10.0-beta.415",
            "timestamp": "2025-10-23T19:08:22Z",
            "deployment": "ServiceFabric",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__ = MagicMock()

        with patch("httpx.Client", return_value=mock_client):
            version = _get_version_from_api("https://custom.domain.com")
            assert version == "25.10.0-beta.415"

    def test_get_version_from_api_timeout(self):
        """Test _get_version_from_api handles timeouts gracefully."""
        mock_client = MagicMock()
        mock_client.get.side_effect = TimeoutError
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__ = MagicMock()

        with patch("httpx.Client", return_value=mock_client):
            version = _get_version_from_api("https://custom.domain.com")
            assert version is None

    def test_get_version_from_api_network_error(self):
        """Test _get_version_from_api handles network errors gracefully."""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__ = MagicMock()

        with patch("httpx.Client", return_value=mock_client):
            version = _get_version_from_api("https://custom.domain.com")
            assert version is None

    @pytest.mark.parametrize(
        "domain,mock_version,expected_config",
        [
            # Cloud domains should always use auth_config_cloud.json
            ("https://alpha.uipath.com", None, "auth_config_cloud.json"),
            ("https://staging.uipath.com", None, "auth_config_cloud.json"),
            ("https://cloud.uipath.com", None, "auth_config_cloud.json"),
            # Version 25.10.* should use auth_config_25_10.json
            (
                "https://custom.domain.com",
                "25.10.0-beta.415",
                "auth_config_25_10.json",
            ),
            ("https://custom.domain.com", "25.10.1", "auth_config_25_10.json"),
            # Other versions should fallback to cloud config
            ("https://custom.domain.com", "24.10.0", "auth_config_cloud.json"),
            ("https://custom.domain.com", "26.1.0", "auth_config_cloud.json"),
            # Unable to determine version should fallback to cloud config
            ("https://custom.domain.com", None, "auth_config_cloud.json"),
        ],
    )
    def test_select_config_file(self, domain, mock_version, expected_config):
        """Test _select_config_file selects the correct config based on domain and version."""
        with patch(
            "uipath._cli._auth._oidc_utils._get_version_from_api",
            return_value=mock_version,
        ):
            config_file = _select_config_file(domain)
            assert config_file == expected_config

    def test_get_auth_config_without_domain(self):
        """Test get_auth_config without domain parameter uses default config."""
        with patch(
            "uipath._cli._auth._oidc_utils.OidcUtils._find_free_port", return_value=8104
        ):
            config = OidcUtils.get_auth_config()
            assert config["client_id"] == "36dea5b8-e8bb-423d-8e7b-c808df8f1c00"
            assert config["port"] == 8104

    def test_get_auth_config_with_cloud_domain(self):
        """Test get_auth_config with cloud domain uses auth_config_cloud.json."""
        with patch(
            "uipath._cli._auth._oidc_utils.OidcUtils._find_free_port", return_value=8104
        ):
            config = OidcUtils.get_auth_config("https://alpha.uipath.com")
            assert config["client_id"] == "36dea5b8-e8bb-423d-8e7b-c808df8f1c00"
            assert config["port"] == 8104

    def test_get_auth_config_with_25_10_version(self):
        """Test get_auth_config with version 25.10 uses auth_config_25_10.json."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"version": "25.10.0-beta.415"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__ = MagicMock()

        with (
            patch("httpx.Client", return_value=mock_client),
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils._find_free_port",
                return_value=8104,
            ),
        ):
            config = OidcUtils.get_auth_config("https://custom.domain.com")
            assert config["client_id"] == "36dea5b8-e8bb-423d-8e7b-c808df8f1c00"
            assert config["port"] == 8104
