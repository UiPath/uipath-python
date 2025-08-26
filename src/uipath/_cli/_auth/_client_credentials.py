from typing import Optional
from urllib.parse import urlparse

import httpx

from ..._utils._ssl_context import get_httpx_client_kwargs
from .._utils._console import ConsoleLogger
from ._models import TokenData
from ._utils import parse_access_token, update_env_file

console = ConsoleLogger()


class ClientCredentialsService:
    """Service for client credentials authentication flow."""

    def __init__(self, domain: str):
        self.domain = domain

    def get_token_url(self) -> str:
        """Get the token URL for the specified domain."""
        match self.domain:
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

    def extract_domain_from_base_url(self, base_url: str) -> str:
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

    def authenticate(
        self, client_id: str, client_secret: str, scope: Optional[str] = "OR.Execution"
    ) -> Optional[TokenData]:
        """Authenticate using client credentials flow.

        Args:
            client_id: The client ID for authentication
            client_secret: The client secret for authentication
            scope: The scope for the token (default: OR.Execution)

        Returns:
            Token data if successful, None otherwise
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
                        token_data = response.json()
                        return {
                            "access_token": token_data["access_token"],
                            "token_type": token_data.get("token_type", "Bearer"),
                            "expires_in": token_data.get("expires_in", 3600),
                            "scope": token_data.get("scope", scope),
                            # Client credentials flow doesn't provide these, but we need them for compatibility
                            "refresh_token": "",
                            "id_token": "",
                        }
                    case 400:
                        console.error(
                            "Invalid client credentials or request parameters."
                        )
                        return None
                    case 401:
                        console.error("Unauthorized: Invalid client credentials.")
                        return None
                    case _:
                        console.error(
                            f"Authentication failed: {response.status_code} - {response.text}"
                        )
                        return None

        except httpx.RequestError as e:
            console.error(f"Network error during authentication: {e}")
            return None
        except Exception as e:
            console.error(f"Unexpected error during authentication: {e}")
            return None

    def setup_environment(self, token_data: TokenData, base_url: str):
        """Setup environment variables for client credentials authentication.

        Args:
            token_data: The token data from authentication
            base_url: The base URL for the UiPath instance
        """
        parsed_access_token = parse_access_token(token_data["access_token"])

        env_vars = {
            "UIPATH_ACCESS_TOKEN": token_data["access_token"],
            "UIPATH_URL": base_url,
            "UIPATH_ORGANIZATION_ID": parsed_access_token.get("prt_id", ""),
            "UIPATH_TENANT_ID": "",
        }

        update_env_file(env_vars)
