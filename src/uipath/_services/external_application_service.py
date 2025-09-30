from os import environ as env
from typing import Optional
from urllib.parse import urlparse

import httpx
from httpx import HTTPStatusError, Request

from .._utils._ssl_context import get_httpx_client_kwargs
from .._utils.constants import ENV_BASE_URL
from ..models.auth import TokenData
from ..models.exceptions import EnrichedException


class ExternalApplicationService:
    """Service for client credentials authentication flow."""

    def __init__(self, base_url: Optional[str]):
        if not (resolved_base_url := (base_url or env.get(ENV_BASE_URL))):
            raise ValueError(
                "Base URL must be set either via constructor or the BASE_URL environment variable."
            )
        self._base_url = resolved_base_url
        self._domain = self._extract_environment_from_base_url(self._base_url)

    def get_token_url(self) -> str:
        """Get the token URL for the specified domain."""
        match self._domain:
            case "alpha":
                return "https://alpha.uipath.com/identity_/connect/token"
            case "staging":
                return "https://staging.uipath.com/identity_/connect/token"
            case _:  # cloud (default)
                return "https://cloud.uipath.com/identity_/connect/token"

    def _is_valid_domain_or_subdomain(self, hostname: str, domain: str) -> bool:
        """Check if hostname is either an exact match or a valid subdomain of the domain.

        Args:
            hostname: The hostname to check
            domain: The domain to validate against

        Returns:
            True if hostname is valid domain or subdomain, False otherwise
        """
        return hostname == domain or hostname.endswith(f".{domain}")

    def _extract_environment_from_base_url(self, base_url: str) -> str:
        """Extract domain from base URL.

        Args:
            base_url: The base URL to extract domain from

        Returns:
            The domain (alpha, staging, or cloud)
        """
        try:
            parsed = urlparse(base_url)
            hostname = parsed.hostname

            if hostname:
                match hostname:
                    case h if self._is_valid_domain_or_subdomain(h, "alpha.uipath.com"):
                        return "alpha"
                    case h if self._is_valid_domain_or_subdomain(
                        h, "staging.uipath.com"
                    ):
                        return "staging"
                    case h if self._is_valid_domain_or_subdomain(h, "cloud.uipath.com"):
                        return "cloud"

            # Default to cloud if we can't determine
            return "cloud"
        except Exception:
            # Default to cloud if parsing fails
            return "cloud"

    def get_token_data(
        self, client_id: str, client_secret: str, scope: Optional[str] = "OR.Execution"
    ) -> TokenData:
        """Authenticate using client credentials flow.

        Args:
            client_id: The client ID for authentication
            client_secret: The client secret for authentication
            scope: The scope for the token (default: OR.Execution)

        Returns:
            Token data if successful
        """
        token_url = self.get_token_url()

        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        }

        try:
            with httpx.Client(**get_httpx_client_kwargs()) as client:
                response = client.post(token_url, data=data)
                match response.status_code:
                    case 200:
                        return TokenData.model_validate(response.json())
                    case 400:
                        raise EnrichedException(
                            HTTPStatusError(
                                message="Invalid client credentials or request parameters.",
                                request=Request(
                                    data=data, url=token_url, method="post"
                                ),
                                response=response,
                            )
                        )
                    case 401:
                        raise EnrichedException(
                            HTTPStatusError(
                                message="Unauthorized: Invalid client credentials.",
                                request=Request(
                                    data=data, url=token_url, method="post"
                                ),
                                response=response,
                            )
                        )
                    case _:
                        raise EnrichedException(
                            HTTPStatusError(
                                message=f"Authentication failed with unexpected status: {response.status_code}",
                                request=Request(
                                    data=data, url=token_url, method="post"
                                ),
                                response=response,
                            )
                        )
        except EnrichedException:
            raise
        except httpx.RequestError as e:
            raise Exception(f"Network error during authentication: {e}") from e
        except Exception as e:
            raise Exception(f"Unexpected error during authentication: {e}") from e
