import base64
import hashlib
import json
import os
from urllib.parse import urlencode

from ._models import AuthConfig


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


def get_auth_config() -> AuthConfig:
    auth_config = {}
    with open(os.path.join(os.path.dirname(__file__), "auth_config.json"), "r") as f:
        auth_config = json.load(f)
    if "UIPATH_URL" in os.environ:
        url = os.environ["UIPATH_URL"]
        # Expected format: https://{domain}.uipath.com/{account}/{tenant}
        parts = url.strip("/").split("/")
        if len(parts) >= 3:
            domain = parts[2].split(".")[0]
            account = parts[3]
            auth_config["domain"] = domain
            auth_config["account"] = account
    else:
        raise ValueError("[auth] UIPATH_URL is not set")
    if "client_id" not in auth_config:
        raise ValueError("[auth] client_id is not set")
    if "redirect_uri" not in auth_config:
        raise ValueError("[auth] redirect_uri is not set")
    if "scope" not in auth_config:
        raise ValueError("[auth] scope is not set")
    if "domain" not in auth_config:
        raise ValueError("[auth] domain is not set")
    if "account" not in auth_config:
        raise ValueError("[auth] account is not set")

    return AuthConfig(
        client_id=auth_config["client_id"],
        redirect_uri=auth_config["redirect_uri"],
        scope=auth_config["scope"],
        port=auth_config.get("port", 6234),
    )


def get_auth_url(domain: str) -> tuple[str, str, str]:
    """Get the authorization URL for OAuth2 PKCE flow.

    Args:
        domain (str): The UiPath domain to authenticate against (e.g. 'alpha', 'cloud')

    Returns:
        tuple[str, str]: A tuple containing:
            - The authorization URL with query parameters
            - The code verifier for PKCE flow
    """
    code_verifier, code_challenge = generate_code_verifier_and_challenge()
    auth_config = get_auth_config()
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
    url = f"https://{domain}.uipath.com/identity_/connect/authorize?{query_string}"
    return url, code_verifier, state
