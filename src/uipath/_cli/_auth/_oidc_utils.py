import base64
import hashlib
import json
import os
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx

from ..._utils._ssl_context import get_httpx_client_kwargs
from .._utils._console import ConsoleLogger
from ._models import AuthConfig
from ._url_utils import build_service_url


def generate_code_verifier_and_challenge():
    """Generate PKCE code verifier and challenge."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")

    code_challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(code_challenge_bytes).decode("utf-8").rstrip("=")
    )

    return code_verifier, code_challenge


def get_state_param() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")


def _get_version_from_api(domain: str) -> Optional[str]:
    """Fetch the version from the UiPath orchestrator API.

    Args:
        domain: The UiPath domain (e.g., 'https://alpha.uipath.com')

    Returns:
        The version string (e.g., '25.10.0-beta.415') or None if unable to fetch
    """
    try:
        version_url = build_service_url(domain, "/orchestrator_/api/status/version")
        client_kwargs = get_httpx_client_kwargs()
        # Override timeout for version check
        client_kwargs["timeout"] = 5.0

        with httpx.Client(**client_kwargs) as client:
            response = client.get(version_url)
            response.raise_for_status()
            data = response.json()
            return data.get("version")
    except Exception:
        # Silently fail and return None if we can't fetch the version
        return None


def _is_cloud_domain(domain: str) -> bool:
    """Check if the domain is a cloud domain (alpha, staging, or cloud.uipath.com).

    Args:
        domain: The domain string (e.g., 'https://alpha.uipath.com')

    Returns:
        True if it's a cloud domain, False otherwise
    """
    parsed = urlparse(domain)
    netloc = parsed.netloc.lower()
    return netloc in [
        "alpha.uipath.com",
        "staging.uipath.com",
        "cloud.uipath.com",
    ]


def _select_config_file(domain: str) -> str:
    """Select the appropriate auth config file based on domain and version.

    Logic:
    1. If domain is alpha/staging/cloud.uipath.com -> use auth_config_cloud.json
    2. Otherwise, try to get version from API
    3. If version starts with '25.10' -> use auth_config_25_10.json
    4. If version can't be determined -> fallback to auth_config_cloud.json
    5. Otherwise -> fallback to auth_config_cloud.json

    Args:
        domain: The UiPath domain

    Returns:
        The filename of the config to use
    """
    # Check if it's a known cloud domain
    if _is_cloud_domain(domain):
        return "auth_config_cloud.json"

    # Try to get version from API
    version = _get_version_from_api(domain)

    # If we can't determine version, fallback to cloud config
    if version is None:
        return "auth_config_cloud.json"

    # Check if version is 25.10.*
    if version.startswith("25.10"):
        return "auth_config_25_10.json"

    # Default fallback to cloud config
    return "auth_config_cloud.json"


class OidcUtils:
    _console = ConsoleLogger()

    @classmethod
    def _find_free_port(cls, candidates: list[int]):
        from socket import AF_INET, SOCK_STREAM, error, socket

        def is_free(port: int) -> bool:
            with socket(AF_INET, SOCK_STREAM) as s:
                try:
                    s.bind(("localhost", port))
                    return True
                except error:
                    return False

        return next((p for p in candidates if is_free(p)), None)

    @classmethod
    def get_auth_config(cls, domain: Optional[str] = None) -> AuthConfig:
        """Get the appropriate auth configuration based on domain.

        Args:
            domain: The UiPath domain (e.g., 'https://cloud.uipath.com').
                   If None, uses default auth_config_cloud.json

        Returns:
            AuthConfig with the appropriate configuration
        """
        # Select the appropriate config file based on domain
        if domain:
            config_file = _select_config_file(domain)
        else:
            config_file = "auth_config_cloud.json"

        config_path = os.path.join(os.path.dirname(__file__), config_file)
        with open(config_path, "r") as f:
            auth_config = json.load(f)

        custom_port = os.getenv("UIPATH_AUTH_PORT")
        candidates = [int(custom_port)] if custom_port else [8104, 8055, 42042]

        port = cls._find_free_port(candidates)
        if port is None:
            ports_str = ", ".join(str(p) for p in candidates)
            cls._console.error(
                f"All configured ports ({ports_str}) are in use. Please close applications using these ports or configure different ports."
            )

        redirect_uri = auth_config["redirect_uri"].replace(
            "__PY_REPLACE_PORT__", str(port)
        )

        return AuthConfig(
            client_id=auth_config["client_id"],
            redirect_uri=redirect_uri,
            scope=auth_config["scope"],
            port=port,
        )

    @classmethod
    def get_auth_url(cls, domain: str, auth_config: AuthConfig) -> tuple[str, str, str]:
        """Get the authorization URL for OAuth2 PKCE flow.

        Args:
            domain (str): The UiPath domain to authenticate against (e.g. 'alpha', 'cloud')
            auth_config (AuthConfig): The authentication configuration to use

        Returns:
            tuple[str, str]: A tuple containing:
                - The authorization URL with query parameters
                - The code verifier for PKCE flow
        """
        code_verifier, code_challenge = generate_code_verifier_and_challenge()
        state = get_state_param()
        query_params = {
            "client_id": auth_config["client_id"],
            "redirect_uri": auth_config["redirect_uri"],
            "response_type": "code",
            "scope": auth_config["scope"],
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        query_string = urlencode(query_params)
        url = build_service_url(domain, f"/identity_/connect/authorize?{query_string}")
        return url, code_verifier, state
