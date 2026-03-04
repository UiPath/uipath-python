"""
Unit tests for the PortalService.post_refresh_token_request method.

This test suite covers the following scenarios for the token refresh logic:

1. **UIPATH_URL Environment Variable**:
   Ensures the refresh token request correctly uses the domain from the UIPATH_URL
   environment variable when calling the token endpoint.

2. **Alpha, Staging, Cloud Domains**:
   Verifies that the refresh token request works correctly with different UiPath domains
   (alpha.uipath.com, staging.uipath.com, cloud.uipath.com).

3. **Custom Domain**:
   Tests that the refresh token request works with custom automation suite domains.

4. **Error Handling**:
   Tests proper error handling for various HTTP status codes (401, 500, etc.).

5. **Client Initialization**:
   Tests that the method properly handles uninitialized HTTP client scenarios.
"""

import os
from unittest.mock import Mock, patch

import httpx
import pytest

from uipath._cli._auth._auth_service import AuthService
from uipath._cli._auth._portal_service import PortalService


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


class TestPortalServiceRefreshToken:
    """Test class for PortalService refresh token functionality."""

    @pytest.mark.parametrize(
        "environment, expected_token_url",
        [
            # Standard UiPath domains
            ("cloud", "https://cloud.uipath.com/identity_/connect/token"),
            ("alpha", "https://alpha.uipath.com/identity_/connect/token"),
            ("staging", "https://staging.uipath.com/identity_/connect/token"),
        ],
    )
    def test_post_refresh_token_request_different_domains(
        self, environment, expected_token_url, mock_auth_config, sample_token_data
    ):
        """Test refresh token request with different domain configurations."""

        with patch(
            "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
            return_value=mock_auth_config,
        ):
            # Create a mock HTTP client
            mock_client = Mock(spec=httpx.Client)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_token_data
            mock_client.post.return_value = mock_response

            # Create AuthService instance
            auth_service = AuthService(environment=environment, force=False)

            # Create PortalService instance
            portal_service = PortalService(auth_service._domain)
            portal_service._client = mock_client

            # Test refresh token request
            refresh_token = "test_refresh_token"
            result = portal_service.refresh_access_token(refresh_token)

            # Verify the correct URL was called
            mock_client.post.assert_called_once_with(
                expected_token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": mock_auth_config["client_id"],
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Verify the response
            assert result.access_token == sample_token_data["access_token"]
            assert result.refresh_token == sample_token_data["refresh_token"]

    @pytest.mark.parametrize(
        "env_var_url, environment, expected_token_url",
        [
            # UIPATH_URL should be used when environment is None (no flag specified)
            (
                "https://custom.automationsuite.org/org/tenant",
                None,
                "https://custom.automationsuite.org/identity_/connect/token",
            ),
            (
                "https://mycompany.uipath.com/org/tenant/",
                None,
                "https://mycompany.uipath.com/identity_/connect/token",
            ),
            # Explicit environment flags should override UIPATH_URL
            (
                "https://custom.automationsuite.org/org/tenant",
                "alpha",
                "https://alpha.uipath.com/identity_/connect/token",
            ),
            (
                "https://custom.automationsuite.org/org/tenant",
                "staging",
                "https://staging.uipath.com/identity_/connect/token",
            ),
            (
                "https://custom.automationsuite.org/org/tenant",
                "cloud",
                "https://cloud.uipath.com/identity_/connect/token",
            ),
        ],
    )
    def test_post_refresh_token_request_with_uipath_url_env(
        self,
        env_var_url,
        environment,
        expected_token_url,
        mock_auth_config,
        sample_token_data,
    ):
        """Test refresh token request with UIPATH_URL environment variable."""

        # Set the environment variable
        original_env = os.environ.get("UIPATH_URL")
        os.environ["UIPATH_URL"] = env_var_url

        try:
            with patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                return_value=mock_auth_config,
            ):
                # Create a mock HTTP client
                mock_client = Mock(spec=httpx.Client)
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = sample_token_data
                mock_client.post.return_value = mock_response

                # Create AuthService instance
                auth_service = AuthService(environment=environment, force=False)

                # Create PortalService instance
                portal_service = PortalService(auth_service._domain)
                portal_service._client = mock_client

                # Test refresh token request
                refresh_token = "test_refresh_token"
                result = portal_service.refresh_access_token(refresh_token)

                # Verify the correct URL was called
                mock_client.post.assert_called_once_with(
                    expected_token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": mock_auth_config["client_id"],
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                # Verify the response
                assert result.access_token == sample_token_data["access_token"]
                assert result.refresh_token == sample_token_data["refresh_token"]

        finally:
            # Clean up environment variable
            if original_env is not None:
                os.environ["UIPATH_URL"] = original_env
            elif "UIPATH_URL" in os.environ:
                del os.environ["UIPATH_URL"]

    def test_post_refresh_token_request_unauthorized(self, mock_auth_config):
        """Test refresh token request with 401 Unauthorized response."""

        with patch(
            "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
            return_value=mock_auth_config,
        ):
            with patch(
                "uipath._cli._auth._portal_service.ConsoleLogger"
            ) as mock_logger_cls:
                mock_console = Mock()
                mock_console.error.side_effect = SystemExit(1)
                mock_logger_cls.return_value = mock_console

                # Create a mock HTTP client
                mock_client = Mock(spec=httpx.Client)
                mock_response = Mock()
                mock_response.status_code = 401
                mock_client.post.return_value = mock_response

                # Create AuthService instance
                auth_service = AuthService(environment="cloud", force=False)

                # Create PortalService instance
                portal_service = PortalService(auth_service._domain)
                portal_service._client = mock_client

                # Test refresh token request - should raise exception due to console.error
                with pytest.raises(SystemExit):
                    portal_service.refresh_access_token("test_refresh_token")

                # Verify error was logged
                mock_console.error.assert_called_once_with("Unauthorized")

    def test_post_refresh_token_request_server_error(self, mock_auth_config):
        """Test refresh token request with 500 server error response."""

        with patch(
            "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
            return_value=mock_auth_config,
        ):
            with patch(
                "uipath._cli._auth._portal_service.ConsoleLogger"
            ) as mock_logger_cls:
                mock_console = Mock()
                mock_console.error.side_effect = SystemExit(1)
                mock_logger_cls.return_value = mock_console

                # Create a mock HTTP client
                mock_client = Mock(spec=httpx.Client)
                mock_response = Mock()
                mock_response.status_code = 500
                mock_client.post.return_value = mock_response

                # Create AuthService instance
                auth_service = AuthService(environment="cloud", force=False)

                # Create PortalService instance
                portal_service = PortalService(auth_service._domain)
                portal_service._client = mock_client

                # Test refresh token request - should raise exception due to console.error
                with pytest.raises(SystemExit):
                    portal_service.refresh_access_token("test_refresh_token")

                # Verify error was logged
                mock_console.error.assert_called_once_with(
                    "Failed to refresh token: 500"
                )

    def test_refresh_token_lazy_initializes_client(
        self, mock_auth_config, sample_token_data
    ):
        portal_service = PortalService("https://cloud.uipath.com")
        assert portal_service._client is None

        with patch("httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.post.return_value.status_code = 200
            mock_client.post.return_value.json.return_value = sample_token_data
            mock_client_cls.return_value = mock_client

            result = portal_service.refresh_access_token("test_refresh_token")

            assert portal_service._client is mock_client
            assert result.access_token == sample_token_data["access_token"]

    def test_post_refresh_token_request_success_response_format(
        self, mock_auth_config, sample_token_data
    ):
        """Test that successful refresh token request returns proper TokenData format."""

        with patch(
            "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
            return_value=mock_auth_config,
        ):
            # Create a mock HTTP client
            mock_client = Mock(spec=httpx.Client)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_token_data
            mock_client.post.return_value = mock_response

            # Create AuthService instance
            auth_service = AuthService(environment="cloud", force=False)

            # Create PortalService instance
            portal_service = PortalService(auth_service._domain)
            portal_service._client = mock_client

            # Test refresh token request
            result = portal_service.refresh_access_token("test_refresh_token")

            # Verify result is a TokenData model with all expected fields
            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.expires_in is not None
            assert result.token_type is not None
            assert result.scope is not None
            assert result.id_token is not None

            # Verify values match expected
            assert result.access_token == sample_token_data["access_token"]
            assert result.refresh_token == sample_token_data["refresh_token"]

    def test_post_refresh_token_request_malformed_domain_handling(
        self, mock_auth_config, sample_token_data
    ):
        """Test refresh token request with various domain formats."""

        test_cases = [
            # Domain with trailing slash should not create double slash
            (
                "https://example.uipath.com/",
                None,
                "https://example.uipath.com/identity_/connect/token",
            ),
            # Domain without scheme gets .uipath.com appended (current behavior)
            (
                "https://example.com/",
                "example",
                "https://example.uipath.com/identity_/connect/token",
            ),
            # Domain with path should use base only
            (
                "https://example.com/some/path",
                "example",
                "https://example.uipath.com/identity_/connect/token",
            ),
        ]

        for uipath_url, environment, expected_url in test_cases:
            with patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                return_value=mock_auth_config,
            ):
                os.environ["UIPATH_URL"] = uipath_url

                # Create a mock HTTP client
                mock_client = Mock(spec=httpx.Client)
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = sample_token_data
                mock_client.post.return_value = mock_response

                # Create AuthService instance
                auth_service = AuthService(environment=environment, force=False)

                # Create PortalService instance
                portal_service = PortalService(auth_service._domain)
                portal_service._client = mock_client

                # Test refresh token request
                portal_service.refresh_access_token("test_refresh_token")

                # Verify the correct URL was called
                mock_client.post.assert_called_with(
                    expected_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": "test_refresh_token",
                        "client_id": mock_auth_config["client_id"],
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                # Reset mock for next iteration
                mock_client.reset_mock()

    @pytest.mark.parametrize(
        "scenario_name, env_vars, environment, expected_token_url",
        [
            # These scenarios mirror the test_auth.py test cases but focus on the refresh token endpoint
            (
                "refresh_with_uipath_url_env_variable",
                {"UIPATH_URL": "https://custom.automationsuite.org/org/tenant"},
                None,  # None when no flag specified
                "https://custom.automationsuite.org/identity_/connect/token",
            ),
            (
                "refresh_with_uipath_url_env_variable_with_trailing_slash",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant/"},
                None,
                "https://custom.uipath.com/identity_/connect/token",
            ),
            (
                "refresh_with_alpha_flag_overrides_env",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "alpha",  # alpha flag overrides UIPATH_URL
                "https://alpha.uipath.com/identity_/connect/token",
            ),
            (
                "refresh_with_staging_flag_overrides_env",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "staging",  # staging flag overrides UIPATH_URL
                "https://staging.uipath.com/identity_/connect/token",
            ),
            (
                "refresh_with_cloud_flag_overrides_env",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "cloud",  # cloud flag overrides UIPATH_URL
                "https://cloud.uipath.com/identity_/connect/token",
            ),
            (
                "refresh_default_to_cloud",
                {},
                None,  # None defaults to cloud
                "https://cloud.uipath.com/identity_/connect/token",
            ),
        ],
    )
    def test_post_refresh_token_request_auth_scenarios_integration(
        self,
        scenario_name,
        env_vars,
        environment,
        expected_token_url,
        mock_auth_config,
        sample_token_data,
    ):
        """Test refresh token request integration with all auth command scenarios from test_auth.py."""

        # Store original environment variables
        original_env_vars = {}
        for key in env_vars:
            original_env_vars[key] = os.environ.get(key)

        try:
            # Set test environment variables
            for key, value in env_vars.items():
                os.environ[key] = value

            with patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                return_value=mock_auth_config,
            ):
                # Create a mock HTTP client
                mock_client = Mock(spec=httpx.Client)
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = sample_token_data
                mock_client.post.return_value = mock_response

                # Create AuthService instance
                auth_service = AuthService(environment=environment, force=False)

                # Create PortalService instance with the domain that would be determined
                # by the auth command logic
                portal_service = PortalService(auth_service._domain)
                portal_service._client = mock_client

                # Test refresh token request
                result = portal_service.refresh_access_token("test_refresh_token")

                # Verify the correct URL was called
                mock_client.post.assert_called_once_with(
                    expected_token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": "test_refresh_token",
                        "client_id": mock_auth_config["client_id"],
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                # Verify the response
                assert result.access_token == sample_token_data["access_token"]
                assert result.refresh_token == sample_token_data["refresh_token"]

        finally:
            # Restore original environment variables
            for key, original_value in original_env_vars.items():
                if original_value is not None:
                    os.environ[key] = original_value
                elif key in os.environ:
                    del os.environ[key]
