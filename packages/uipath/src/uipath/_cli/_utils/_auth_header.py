"""Bearer header for connections the CLI opens."""

import os
from collections.abc import Mapping

from uipath.platform.common._token_renewal import token_renewal_running
from uipath.platform.constants import ENV_UIPATH_ACCESS_TOKEN


def with_current_access_token(headers: Mapping[str, str]) -> dict[str, str]:
    """Copy ``headers``; while the token is renewed, an existing ``Authorization`` gets the environment's token."""
    result = dict(headers)
    if not token_renewal_running():
        return result
    token = os.environ.get(ENV_UIPATH_ACCESS_TOKEN)
    if token and "Authorization" in result:
        result["Authorization"] = f"Bearer {token}"
    return result
