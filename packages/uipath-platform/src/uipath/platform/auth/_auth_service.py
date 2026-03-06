import json
import logging
import os
import time
from functools import cached_property
from urllib.parse import urlencode

import httpx

from uipath.platform.common._http_config import get_httpx_client_kwargs
from uipath.platform.common.auth import TokenData

from ._errors import AuthenticationError
from ._models import (
    AuthConfig,
    AuthorizationRequest,
    TenantsAndOrganizationInfoResponse,
)
from ._oidc_utils import (
    _select_config_file,
    generate_code_verifier_and_challenge,
    get_state_param,
)
from ._url_utils import build_service_url
from ._utils import parse_access_token

_logger = logging.getLogger(__name__)


class AuthService:
    """Service for UiPath OAuth2 authentication and portal API operations.

    Provides the full OAuth2 Authorization Code + PKCE flow for obtaining
    user tokens, as well as token refresh and tenant/organization discovery.

    This is a standalone service that does not inherit from ``BaseService``
    because it operates before an access token is available (i.e., it is used
    to *obtain* the token that other services require).

    Args:
        domain: The UiPath domain (e.g., ``https://cloud.uipath.com``).

    Examples:
        **Obtain a user token using the OAuth2 PKCE flow:**

        ```python
        import asyncio
        from uipath.platform.auth import AuthService

        auth = AuthService("https://cloud.uipath.com")

        # 1. Build the authorization URL
        redirect_uri = "http://localhost:8104/oidc/login"
        auth_request = auth.get_authorization_url(redirect_uri)
        print(f"Open this URL in your browser: {auth_request.url}")

        # 2. After user authorizes, exchange the code for tokens
        token_data = asyncio.run(
            auth.exchange_authorization_code(
                code="<authorization_code>",
                code_verifier=auth_request.code_verifier,
                redirect_uri=redirect_uri,
            )
        )
        print(f"Access token: {token_data.access_token}")
        ```

        **Refresh an expired token:**

        ```python
        import asyncio
        from uipath.platform.auth import AuthService

        auth = AuthService("https://cloud.uipath.com")

        # ensure_valid_token returns the same token if still valid,
        # or refreshes it automatically if expired
        refreshed = asyncio.run(auth.ensure_valid_token(token_data))
        ```

        **Discover available tenants:**

        ```python
        import asyncio
        from uipath.platform.auth import AuthService

        auth = AuthService("https://cloud.uipath.com")
        info = asyncio.run(
            auth.get_tenants_and_organizations(token_data.access_token)
        )
        for tenant in info["tenants"]:
            print(f"{tenant['name']} ({tenant['id']})")
        ```
    """

    def __init__(self, domain: str):
        self.domain = domain

    @cached_property
    def auth_config(self) -> AuthConfig:
        """Get the OIDC auth configuration for this domain.

        The configuration is automatically selected based on the domain
        and the server version (cloud vs. on-premise 25.10).
        The result is cached after the first access.

        Returns:
            AuthConfig with client_id and scope.
        """
        config_file = _select_config_file(self.domain)
        config_path = os.path.join(os.path.dirname(__file__), config_file)
        with open(config_path, "r") as f:
            raw = json.load(f)
        return AuthConfig(client_id=raw["client_id"], scope=raw["scope"])

    def get_authorization_url(self, redirect_uri: str) -> AuthorizationRequest:
        """Build the authorization URL for the OAuth2 PKCE flow.

        Generates a PKCE code verifier/challenge pair and a random state
        parameter, then constructs the full authorization URL.

        Args:
            redirect_uri: The redirect URI for the OAuth callback
                (e.g., ``http://localhost:8104/oidc/login``).

        Returns:
            AuthorizationRequest containing the authorization URL,
                the code verifier (needed for token exchange), and the state.

        Examples:
            ```python
            from uipath.platform.auth import AuthService

            auth = AuthService("https://cloud.uipath.com")
            request = auth.get_authorization_url("http://localhost:8104/oidc/login")

            # Open request.url in the browser
            # After redirect, use request.code_verifier to exchange the code
            ```
        """
        code_verifier, code_challenge = generate_code_verifier_and_challenge()
        state = get_state_param()
        query_params = {
            "client_id": self.auth_config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.auth_config.scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        url = build_service_url(
            self.domain, f"/identity_/connect/authorize?{urlencode(query_params)}"
        )
        return AuthorizationRequest(url=url, code_verifier=code_verifier, state=state)

    async def exchange_authorization_code(
        self, code: str, code_verifier: str, redirect_uri: str
    ) -> TokenData:
        """Exchange an authorization code for tokens (PKCE flow).

        Args:
            code: The authorization code received from the OAuth callback.
            code_verifier: The PKCE code verifier from ``get_authorization_url``.
            redirect_uri: The redirect URI (must match the one used in the auth URL).

        Returns:
            TokenData with access_token, refresh_token, expires_in, etc.

        Raises:
            AuthenticationError: If the token exchange fails.

        Examples:
            ```python
            import asyncio
            from uipath.platform.auth import AuthService

            auth = AuthService("https://cloud.uipath.com")
            token_data = asyncio.run(
                auth.exchange_authorization_code(
                    code="abc123",
                    code_verifier=auth_request.code_verifier,
                    redirect_uri="http://localhost:8104/oidc/login",
                )
            )
            ```
        """
        url = build_service_url(self.domain, "/identity_/connect/token")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "client_id": self.auth_config.client_id,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
            response = await client.post(url, data=data, headers=headers)

        if response.status_code >= 400:
            raise AuthenticationError(
                f"Failed to exchange authorization code: {response.status_code}"
            )

        return TokenData.model_validate(response.json())

    async def ensure_valid_token(self, token_data: TokenData) -> TokenData:
        """Check if the token is still valid; refresh it if expired.

        Parses the JWT ``exp`` claim from the access token. If the token
        is still valid, returns it as-is. If expired, uses the refresh
        token to obtain a new one.

        Args:
            token_data: The current token data to validate.

        Returns:
            The same TokenData if still valid, or a freshly refreshed one.

        Raises:
            AuthenticationError: If no refresh token is available or the
                refresh request fails.

        Examples:
            ```python
            import asyncio
            from uipath.platform.auth import AuthService, get_auth_data

            auth = AuthService("https://cloud.uipath.com")
            current_token = get_auth_data()
            valid_token = asyncio.run(auth.ensure_valid_token(current_token))
            ```
        """
        claims = parse_access_token(token_data.access_token)
        exp = claims.get("exp")

        if exp is not None and float(exp) > time.time():
            return token_data

        if not token_data.refresh_token:
            raise AuthenticationError("No refresh token found. Please re-authenticate.")

        return await self._refresh_access_token(token_data.refresh_token)

    async def get_tenants_and_organizations(
        self, access_token: str
    ) -> TenantsAndOrganizationInfoResponse:
        """Get available tenants and organization info for the authenticated user.

        Args:
            access_token: A valid access token.

        Returns:
            Response containing a list of tenants and the organization info.

        Raises:
            AuthenticationError: If the access token is invalid or the
                request fails.

        Examples:
            ```python
            import asyncio
            from uipath.platform.auth import AuthService

            auth = AuthService("https://cloud.uipath.com")
            info = asyncio.run(
                auth.get_tenants_and_organizations(token_data.access_token)
            )
            org = info["organization"]
            print(f"Organization: {org['name']}")
            for tenant in info["tenants"]:
                print(f"  Tenant: {tenant['name']} ({tenant['id']})")
            ```
        """
        claims = parse_access_token(access_token)
        prt_id = claims.get("prt_id")

        url = build_service_url(
            self.domain,
            f"/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo",
        )
        async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )

        if response.status_code == 401:
            raise AuthenticationError(
                "Unauthorized: access token is invalid or expired."
            )

        if response.status_code >= 400:
            raise AuthenticationError(
                f"Failed to get tenants and organizations: {response.status_code} {response.text}"
            )

        return response.json()

    async def _refresh_access_token(self, refresh_token: str) -> TokenData:
        """Refresh an access token using a refresh token."""
        url = build_service_url(self.domain, "/identity_/connect/token")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.auth_config.client_id,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
            response = await client.post(url, data=data, headers=headers)

        if response.status_code == 401:
            raise AuthenticationError(
                "Unauthorized: refresh token is invalid or expired."
            )

        if response.status_code >= 400:
            raise AuthenticationError(
                f"Failed to refresh token: {response.status_code}"
            )

        return TokenData.model_validate(response.json())
