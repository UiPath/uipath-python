import base64
import json
from os import environ as env
from pathlib import Path
from typing import Optional

from .._services import ExternalApplicationService
from .constants import (
    ENV_BASE_URL,
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
)


def parse_access_token(access_token: str):
    token_parts = access_token.split(".")
    if len(token_parts) < 2:
        raise Exception("Invalid access token")
    payload = base64.urlsafe_b64decode(
        token_parts[1] + "=" * (-len(token_parts[1]) % 4)
    )
    return json.loads(payload)


def update_env_file(env_contents):
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    if key not in env_contents:
                        env_contents[key] = value
    lines = [f"{key}={value}\n" for key, value in env_contents.items()]
    with open(env_path, "w") as f:
        f.writelines(lines)


def _has_valid_client_credentials(
    client_id: Optional[str], client_secret: Optional[str]
) -> bool:
    if bool(client_id) != bool(client_secret):
        raise ValueError(
            "Both client_id and client_secret must be provided together for Client Credentials Authentication."
        )
    return bool(client_id and client_secret)


def resolve_config(
    base_url: Optional[str],
    secret: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    scope: Optional[str],
):
    if _has_valid_client_credentials(client_id, client_secret):
        external_app_service = ExternalApplicationService(base_url)
        token_data = external_app_service.get_token_data(
            client_id,  # type: ignore
            client_secret,  # type: ignore
            scope,
        )

        return external_app_service._base_url, token_data.access_token

    base_url_value = base_url or env.get(ENV_BASE_URL)

    secret_value = (
        secret
        or env.get(ENV_UNATTENDED_USER_ACCESS_TOKEN)
        or env.get(ENV_UIPATH_ACCESS_TOKEN)
    )

    return base_url_value, secret_value
