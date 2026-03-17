"""Identity service for UiPath authentication token operations."""

from typing import Optional

import httpx

from ..common._http_config import get_httpx_client_kwargs
from ..common.auth import TokenData


class IdentityService:
    """Service for interacting with the UiPath Identity server."""

    def __init__(self, domain: str):
        """Initialize the IdentityService.

        Args:
            domain: The base URL of the UiPath identity server (e.g., "https://cloud.uipath.com").
        """
        self._domain = domain

    def refresh_access_token(
        self,
        refresh_token: str,
        client_id: str,
    ) -> TokenData:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token to exchange for a new access token.
            client_id: The client ID of the application.

        Returns:
            TokenData containing the new access token and related information.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        url = f"{self._domain}/identity_/connect/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }

        with httpx.Client(**get_httpx_client_kwargs()) as client:
            response = client.post(url, data=data)
            response.raise_for_status()
            return TokenData.model_validate(response.json())

    async def refresh_access_token_async(
        self,
        refresh_token: str,
        client_id: str,
    ) -> TokenData:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token to exchange for a new access token.
            client_id: The client ID of the application.

        Returns:
            TokenData containing the new access token and related information.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        url = f"{self._domain}/identity_/connect/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }

        async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return TokenData.model_validate(response.json())

    def get_client_credentials_token(
        self,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = "OR.Execution",
    ) -> TokenData:
        """Obtain an access token using client credentials grant.

        Args:
            client_id: The client ID of the application.
            client_secret: The client secret of the application.
            scope: The requested OAuth scopes (optional, default: "OR.Execution").

        Returns:
            TokenData containing the access token and related information.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        scope = scope or "OR.Execution"
        url = f"{self._domain}/identity_/connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        }

        with httpx.Client(**get_httpx_client_kwargs()) as client:
            response = client.post(url, data=data)
            response.raise_for_status()
            return TokenData.model_validate(response.json())

    async def get_client_credentials_token_async(
        self,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = "OR.Execution",
    ) -> TokenData:
        """Obtain an access token using client credentials grant.

        Args:
            client_id: The client ID of the application.
            client_secret: The client secret of the application.
            scope: The requested OAuth scopes (optional, default: "OR.Execution").

        Returns:
            TokenData containing the access token and related information.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        scope = scope or "OR.Execution"
        url = f"{self._domain}/identity_/connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        }

        async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return TokenData.model_validate(response.json())
