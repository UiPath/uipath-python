from os import environ as env
from typing import Optional

from .._services import ExternalApplicationService
from .constants import ENV_UIPATH_ACCESS_TOKEN, ENV_UNATTENDED_USER_ACCESS_TOKEN


def resolve_secret(
    base_url: Optional[str],
    secret: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    scope: Optional[str],
) -> str | None:
    if client_id and client_secret:
        external_service = ExternalApplicationService(base_url)
        token_data = external_service.get_token_data(client_id, client_secret, scope)
        return token_data["access_token"]

    secret_value = (
        secret
        or env.get(ENV_UNATTENDED_USER_ACCESS_TOKEN)
        or env.get(ENV_UIPATH_ACCESS_TOKEN)
    )

    return secret_value
