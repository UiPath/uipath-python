"""
Unit tests for AuthService._refresh_access_token and ensure_valid_token methods.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uipath.platform.auth import AuthenticationError
from uipath.platform.auth._auth_service import AuthService
from uipath.platform.auth._url_utils import resolve_domain


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


def _make_async_client_mock(response_mock):
    """Create an AsyncClient context manager mock returning the given response."""
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=response_mock)
    mock_client.get = AsyncMock(return_value=response_mock)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestAuthServiceRefreshToken:
    """Test class for AuthService refresh token functionality."""

    @pytest.mark.parametrize(
        "environment, expected_token_url",
        [
            ("cloud", "https://cloud.uipath.com/identity_/connect/token"),
            ("alpha", "https://alpha.uipath.com/identity_/connect/token"),
            ("staging", "https://staging.uipath.com/identity_/connect/token"),
        ],
    )
    @pytest.mark.asyncio
    async def test_refresh_token_different_domains(
        self, environment, expected_token_url, sample_token_data
    ):
        """Test refresh token request with different domain configurations."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_token_data

        mock_client = _make_async_client_mock(mock_response)

        domain = resolve_domain(None, environment)
        service = AuthService(domain)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._refresh_access_token("test_refresh_token")

        mock_client.post.assert_called_once_with(
            expected_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": "test_refresh_token",
                "client_id": service.auth_config.client_id,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert result.access_token == sample_token_data["access_token"]
        assert result.refresh_token == sample_token_data["refresh_token"]

    @pytest.mark.parametrize(
        "env_var_url, environment, expected_token_url",
        [
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
    @pytest.mark.asyncio
    async def test_refresh_token_with_uipath_url_env(
        self,
        env_var_url,
        environment,
        expected_token_url,
        sample_token_data,
    ):
        """Test refresh token request with UIPATH_URL environment variable."""
        original_env = os.environ.get("UIPATH_URL")
        os.environ["UIPATH_URL"] = env_var_url

        try:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_token_data

            mock_client = _make_async_client_mock(mock_response)

            domain = resolve_domain(None, environment)
            service = AuthService(domain)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await service._refresh_access_token("test_refresh_token")

            assert result.access_token == sample_token_data["access_token"]
            assert result.refresh_token == sample_token_data["refresh_token"]
        finally:
            if original_env is not None:
                os.environ["UIPATH_URL"] = original_env
            elif "UIPATH_URL" in os.environ:
                del os.environ["UIPATH_URL"]

    @pytest.mark.asyncio
    async def test_refresh_token_unauthorized(self):
        """Test refresh token request with 401 raises AuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = _make_async_client_mock(mock_response)

        service = AuthService("https://cloud.uipath.com")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AuthenticationError, match="Unauthorized"):
                await service._refresh_access_token("test_refresh_token")

    @pytest.mark.asyncio
    async def test_refresh_token_server_error(self):
        """Test refresh token request with 500 raises AuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = _make_async_client_mock(mock_response)

        service = AuthService("https://cloud.uipath.com")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(
                AuthenticationError, match="Failed to refresh token: 500"
            ):
                await service._refresh_access_token("test_refresh_token")

    @pytest.mark.asyncio
    async def test_refresh_token_response_format(self, sample_token_data):
        """Test successful refresh returns proper TokenData."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_token_data

        mock_client = _make_async_client_mock(mock_response)

        service = AuthService("https://cloud.uipath.com")

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._refresh_access_token("test_refresh_token")

        assert result.access_token == sample_token_data["access_token"]
        assert result.refresh_token == sample_token_data["refresh_token"]
        assert result.expires_in is not None
        assert result.token_type is not None
