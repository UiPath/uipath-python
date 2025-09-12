from os import environ as env
from typing import Optional

from .._services import ExternalApplicationService
from ..models.errors import SecretMissingError
from .constants import ENV_UIPATH_ACCESS_TOKEN, ENV_UNATTENDED_USER_ACCESS_TOKEN


def resolve_secret(
    base_url: str,
    secret: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    scope: Optional[str],
) -> str:
    if client_id and client_secret:
        external_service = ExternalApplicationService(base_url)
        return external_service.get_access_token(client_id, client_secret, scope)

    secret_value = (
        secret
        or env.get(ENV_UNATTENDED_USER_ACCESS_TOKEN)
        or env.get(ENV_UIPATH_ACCESS_TOKEN)
    )

    if not secret_value:
        raise SecretMissingError(
            "Authentication failed. Please provide valid secret or client credentials."
        )

    return secret_value
