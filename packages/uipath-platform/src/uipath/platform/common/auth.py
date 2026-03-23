"""Module defining the TokenData model for authentication tokens."""

from os import environ as env
from typing import Optional

from pydantic import BaseModel
from uipath.platform.common.constants import (
    ENV_BASE_URL,
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
)


class TokenData(BaseModel):
    """Pydantic model for token data structure."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None


def resolve_config_from_env(
    base_url: Optional[str],
    secret: Optional[str],
):
    """Simple config resolution from environment variables."""
    base_url_value = base_url or env.get(ENV_BASE_URL)
    secret_value = (
        secret
        or env.get(ENV_UNATTENDED_USER_ACCESS_TOKEN)
        or env.get(ENV_UIPATH_ACCESS_TOKEN)
    )
    return base_url_value, secret_value
