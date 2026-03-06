import base64
import hashlib
import os
from urllib.parse import urlparse

import httpx

from uipath.platform.common._http_config import get_httpx_client_kwargs

from ._url_utils import build_service_url


def generate_code_verifier_and_challenge() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")

    code_challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(code_challenge_bytes).decode("utf-8").rstrip("=")
    )

    return code_verifier, code_challenge


def get_state_param() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")


def _get_version_from_api(domain: str) -> str | None:
    """Fetch the version from the UiPath orchestrator API."""
    try:
        version_url = build_service_url(domain, "/orchestrator_/api/status/version")
        client_kwargs = get_httpx_client_kwargs()
        client_kwargs["timeout"] = 5.0

        with httpx.Client(**client_kwargs) as client:
            response = client.get(version_url)
            response.raise_for_status()
            data = response.json()
            return data.get("version")
    except Exception:
        return None


def _is_cloud_domain(domain: str) -> bool:
    """Check if the domain is a cloud domain (alpha, staging, or cloud.uipath.com)."""
    parsed = urlparse(domain)
    netloc = parsed.netloc.lower()
    return netloc in [
        "alpha.uipath.com",
        "staging.uipath.com",
        "cloud.uipath.com",
    ]


def _select_config_file(domain: str) -> str:
    """Select the appropriate auth config file based on domain and version."""
    if _is_cloud_domain(domain):
        return "auth_config_cloud.json"

    version = _get_version_from_api(domain)

    if version is None:
        return "auth_config_cloud.json"

    if version.startswith("25.10"):
        return "auth_config_25_10.json"

    return "auth_config_cloud.json"
