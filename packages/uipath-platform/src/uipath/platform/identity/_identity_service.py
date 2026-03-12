"""Identity service for UiPath authentication token operations."""

from typing import Optional

import httpx

from ..common._http_config import get_httpx_client_kwargs
from ..common.auth import TokenData


class IdentityService:
    """Service for interacting with the UiPath Identity server."""

    @staticmethod
    def refresh_access_token(
        domain: str,
        refresh_token: str,
        client_id: str,
    ) -> TokenData:
        """Refresh an access token using a refresh token.

        Args:
            domain: The base URL of the UiPath identity server (e.g., "https://cloud.uipath.com").
            refresh_token: The refresh token to exchange for a new access token.
            client_id: The client ID of the application.

        Returns:
            TokenData containing the new access token and related information.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        url = f"{domain}/identity_/connect/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }

        with httpx.Client(**get_httpx_client_kwargs()) as client:
            response = client.post(url, data=data)
            response.raise_for_status()
            return TokenData.model_validate(response.json())

    @staticmethod
    def get_client_credentials_token(
        domain: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = "OR.Execution",
    ) -> TokenData:
        """Obtain an access token using client credentials grant.

        Args:
            domain: The base URL of the UiPath identity server (e.g., "https://cloud.uipath.com").
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
        url = f"{domain}/identity_/connect/token"
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
