"""
Integration tests for PortalService.ensure_valid_token method.

This test suite ensures that the ensure_valid_token method properly integrates
with the post_refresh_token_request method across all the domain scenarios
described in test_auth.py.
"""

import os
import time
from unittest.mock import Mock, patch

import pytest

from uipath._cli._auth._portal_service import PortalService
from uipath._cli._runtime._contracts import UiPathRuntimeError
from uipath.models.auth import TokenData


@pytest.fixture
def mock_auth_config():
    """Mock auth config fixture."""
    return {
        "client_id": "test_client_id",
        "port": 8104,
        "redirect_uri": "http://localhost:8104/callback",
        "scope": "openid profile offline_access",
    }


@pytest.fixture
def sample_token_data():
    """Sample token data for testing."""
    return {
        "access_token": "new_access_token_123",
        "refresh_token": "new_refresh_token_456",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "openid profile offline_access",
        "id_token": "id_token_789",
    }


@pytest.fixture
def expired_auth_data():
    """Sample expired auth data."""
    return {
        "access_token": "old_access_token",
        "refresh_token": "valid_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "openid profile offline_access",
        "id_token": "old_id_token",
    }


@pytest.fixture
def valid_auth_data():
    """Sample valid (non-expired) auth data."""
    future_time = time.time() + 3600  # 1 hour in the future
    return {
        "access_token": "valid_access_token",
        "refresh_token": "valid_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "openid profile offline_access",
        "id_token": "valid_id_token",
        "exp": future_time,
    }


class TestPortalServiceEnsureValidToken:
    """Test class for PortalService ensure_valid_token functionality."""

    @pytest.mark.parametrize(
        "domain, expected_token_url",
        [
            (
                "https://cloud.uipath.com",
                "https://cloud.uipath.com/identity_/connect/token",
            ),
            (
                "https://alpha.uipath.com",
                "https://alpha.uipath.com/identity_/connect/token",
            ),
            (
                "https://staging.uipath.com",
                "https://staging.uipath.com/identity_/connect/token",
            ),
            (
                "https://custom.automationsuite.org",
                "https://custom.automationsuite.org/identity_/connect/token",
            ),
        ],
    )
    def test_ensure_valid_token_refresh_flow_different_domains(
        self,
        domain,
        expected_token_url,
        mock_auth_config,
        sample_token_data,
        expired_auth_data,
    ):
        """Test ensure_valid_token refresh flow with different domain configurations."""

        # Mock the token as expired
        past_time = time.time() - 3600  # 1 hour ago
        expired_token_claims = {"exp": past_time, "prt_id": "test_prt_id"}

        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._portal_service.get_auth_data",
                return_value=TokenData.model_validate(expired_auth_data),
            ),
            patch(
                "uipath._cli._auth._portal_service.get_parsed_token_data",
                return_value=expired_token_claims,
            ),
            patch(
                "uipath._cli._auth._portal_service.update_auth_file"
            ) as mock_update_auth,
            patch(
                "uipath._cli._auth._portal_service.update_env_file"
            ) as mock_update_env,
            patch.object(PortalService, "_select_tenant"),
        ):
            # Create a mock HTTP client
            mock_client = Mock()

            # Mock the refresh token response
            mock_refresh_response = Mock()
            mock_refresh_response.status_code = 200
            mock_refresh_response.json.return_value = sample_token_data

            # Mock the tenants response
            mock_tenants_response = Mock()
            mock_tenants_response.status_code = 200
            mock_tenants_response.json.return_value = {
                "tenants": [{"name": "DefaultTenant", "id": "tenant-id"}],
                "organization": {"name": "DefaultOrg", "id": "org-id"},
            }

            mock_client.post.return_value = mock_refresh_response
            mock_client.get.return_value = mock_tenants_response

            # Create PortalService instance
            portal_service = PortalService(domain)
            portal_service._client = mock_client

            # Test ensure_valid_token
            portal_service.ensure_valid_token()

            # Verify refresh token request was made to correct URL
            mock_client.post.assert_called_with(
                expected_token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": expired_auth_data["refresh_token"],
                    "client_id": mock_auth_config["client_id"],
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Verify auth file was updated
            mock_update_auth.assert_called_once()
            call_args = mock_update_auth.call_args[0][0]
            assert call_args.access_token == sample_token_data["access_token"]

            # Verify env file was updated
            mock_update_env.assert_called_with(
                {
                    "UIPATH_ACCESS_TOKEN": sample_token_data["access_token"],
                }
            )

    def test_ensure_valid_token_with_valid_token_and_uipath_url_set(
        self, mock_auth_config, valid_auth_data
    ):
        """Test ensure_valid_token when token is still valid and UIPATH_URL is set."""

        # Mock environment variable
        os.environ["UIPATH_URL"] = "https://test.example.com/org/tenant"

        try:
            with (
                patch(
                    "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                    return_value=mock_auth_config,
                ),
                patch(
                    "uipath._cli._auth._portal_service.get_auth_data",
                    return_value=TokenData.model_validate(valid_auth_data),
                ),
                patch(
                    "uipath._cli._auth._portal_service.get_parsed_token_data",
                    return_value=valid_auth_data,
                ),
            ):
                # Create PortalService instance
                portal_service = PortalService("cloud")
                mock_client = Mock()
                portal_service._client = mock_client

                # Test ensure_valid_token
                portal_service.ensure_valid_token()

                # Verify no refresh request was made (token is still valid)
                mock_client.post.assert_not_called()

        finally:
            if "UIPATH_URL" in os.environ:
                del os.environ["UIPATH_URL"]

    def test_ensure_valid_token_missing_refresh_token_raises_exception(
        self, mock_auth_config
    ):
        """Test ensure_valid_token when refresh token is missing."""

        # Auth data without refresh token
        auth_data_no_refresh = {
            "access_token": "old_access_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid profile offline_access",
            "id_token": "old_id_token",
        }

        # Mock the token as expired
        past_time = time.time() - 3600
        expired_token_claims = {"exp": past_time, "prt_id": "test_prt_id"}

        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._portal_service.get_auth_data",
                return_value=TokenData.model_validate(auth_data_no_refresh),
            ),
            patch(
                "uipath._cli._auth._portal_service.get_parsed_token_data",
                return_value=expired_token_claims,
            ),
        ):
            # Create PortalService instance
            portal_service = PortalService("cloud")
            portal_service._client = Mock()

            # Test should raise exception
            with pytest.raises(
                UiPathRuntimeError, match="The refresh token could not be retrieved"
            ):
                portal_service.ensure_valid_token()

    @pytest.mark.parametrize(
        "env_vars, domain",
        [
            ({"UIPATH_URL": "https://custom.automationsuite.org/org/tenant"}, "cloud"),
            ({"UIPATH_URL": "https://custom.uipath.com/org/tenant"}, "alpha"),
            ({}, "staging"),
            ({}, "cloud"),
        ],
    )
    def test_ensure_valid_token_integration_with_auth_scenarios(
        self, env_vars, domain, mock_auth_config, sample_token_data, expired_auth_data
    ):
        """Test ensure_valid_token integration with auth command scenarios."""

        # Store original environment variables
        original_env_vars = {}
        for key in env_vars:
            original_env_vars[key] = os.environ.get(key)

        try:
            # Set test environment variables
            for key, value in env_vars.items():
                os.environ[key] = value

            # Mock the token as expired
            past_time = time.time() - 3600
            expired_token_claims = {"exp": past_time, "prt_id": "test_prt_id"}

            with (
                patch(
                    "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                    return_value=mock_auth_config,
                ),
                patch(
                    "uipath._cli._auth._portal_service.get_auth_data",
                    return_value=TokenData.model_validate(expired_auth_data),
                ),
                patch(
                    "uipath._cli._auth._portal_service.get_parsed_token_data",
                    return_value=expired_token_claims,
                ),
                patch("uipath._cli._auth._portal_service.update_auth_file"),
                patch("uipath._cli._auth._portal_service.update_env_file"),
                patch.object(PortalService, "_select_tenant"),
            ):
                # Create a mock HTTP client
                mock_client = Mock()

                # Mock the refresh token response
                mock_refresh_response = Mock()
                mock_refresh_response.status_code = 200
                mock_refresh_response.json.return_value = sample_token_data

                # Mock the tenants response
                mock_tenants_response = Mock()
                mock_tenants_response.status_code = 200
                mock_tenants_response.json.return_value = {
                    "tenants": [{"name": "DefaultTenant", "id": "tenant-id"}],
                    "organization": {"name": "DefaultOrg", "id": "org-id"},
                }

                mock_client.post.return_value = mock_refresh_response
                mock_client.get.return_value = mock_tenants_response

                # Create PortalService instance
                portal_service = PortalService(domain)
                portal_service._client = mock_client

                # Test ensure_valid_token
                portal_service.ensure_valid_token()

                # Verify refresh was attempted
                assert mock_client.post.called

        finally:
            # Restore original environment variables
            for key, original_value in original_env_vars.items():
                if original_value is not None:
                    os.environ[key] = original_value
                elif key in os.environ:
                    del os.environ[key]
