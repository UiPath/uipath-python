"""
Tests for AuthService.ensure_valid_token method.
"""

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uipath.platform.auth import AuthenticationError
from uipath.platform.auth._auth_service import AuthService
from uipath.platform.common import TokenData


@pytest.fixture
def sample_token_data():
    """Sample refreshed token data."""
    return {
        "access_token": "new_access_token_123",
        "refresh_token": "new_refresh_token_456",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "openid profile offline_access",
        "id_token": "id_token_789",
    }


def _make_async_client_mock(response_mock):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=response_mock)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestAuthServiceEnsureValidToken:
    """Test class for AuthService.ensure_valid_token."""

    @pytest.mark.asyncio
    async def test_returns_same_token_if_still_valid(self):
        """Valid token is returned as-is, no refresh."""
        future_exp = time.time() + 3600
        token_data = TokenData(
            access_token=_make_jwt({"exp": future_exp, "prt_id": "p1"}),
            refresh_token="rt",
            expires_in=3600,
            token_type="Bearer",
            scope="openid",
        )

        service = AuthService("https://cloud.uipath.com")

        with patch("httpx.AsyncClient") as mock_cls:
            result = await service.ensure_valid_token(token_data)

        mock_cls.assert_not_called()
        assert result is token_data

    @pytest.mark.asyncio
    async def test_refreshes_expired_token(self, sample_token_data):
        """Expired token triggers refresh and returns new token."""
        past_exp = time.time() - 3600
        old_token = TokenData(
            access_token=_make_jwt({"exp": past_exp, "prt_id": "p1"}),
            refresh_token="valid_refresh",
            expires_in=3600,
            token_type="Bearer",
            scope="openid",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_token_data
        mock_client = _make_async_client_mock(mock_response)

        service = AuthService("https://cloud.uipath.com")

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.ensure_valid_token(old_token)

        assert result.access_token == sample_token_data["access_token"]
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_if_no_refresh_token(self):
        """Expired token without refresh_token raises AuthenticationError."""
        past_exp = time.time() - 3600
        token_data = TokenData(
            access_token=_make_jwt({"exp": past_exp, "prt_id": "p1"}),
            expires_in=3600,
            token_type="Bearer",
            scope="openid",
        )

        service = AuthService("https://cloud.uipath.com")

        with pytest.raises(AuthenticationError, match="No refresh token found"):
            await service.ensure_valid_token(token_data)

    @pytest.mark.parametrize(
        "domain",
        [
            "https://cloud.uipath.com",
            "https://alpha.uipath.com",
            "https://staging.uipath.com",
            "https://custom.automationsuite.org",
        ],
    )
    @pytest.mark.asyncio
    async def test_refresh_uses_correct_domain(self, domain, sample_token_data):
        """Ensure refresh call goes to the correct domain's token endpoint."""
        past_exp = time.time() - 3600
        old_token = TokenData(
            access_token=_make_jwt({"exp": past_exp, "prt_id": "p1"}),
            refresh_token="rt",
            expires_in=3600,
            token_type="Bearer",
            scope="openid",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_token_data
        mock_client = _make_async_client_mock(mock_response)

        service = AuthService(domain)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await service.ensure_valid_token(old_token)

        expected_url = f"{domain}/identity_/connect/token"
        actual_url = mock_client.post.call_args[0][0]
        assert actual_url == expected_url


def _make_jwt(claims: dict[str, Any]) -> str:
    """Create a minimal JWT with the given claims for testing."""
    import base64
    import json

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.sig"
