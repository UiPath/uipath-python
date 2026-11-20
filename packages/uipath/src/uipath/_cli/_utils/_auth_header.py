"""Bearer header for connections the CLI opens."""

import os
from collections.abc import Mapping

from uipath.platform.constants import ENV_UIPATH_ACCESS_TOKEN


def with_current_access_token(headers: Mapping[str, str]) -> dict[str, str]:
    """Copy ``headers``, with an existing ``Authorization`` set to the environment's token."""
    result = dict(headers)
    token = os.environ.get(ENV_UIPATH_ACCESS_TOKEN)
    if token and "Authorization" in result:
        result["Authorization"] = f"Bearer {token}"
    return result
