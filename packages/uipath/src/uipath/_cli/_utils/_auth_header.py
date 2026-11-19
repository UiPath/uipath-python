"""The bearer header for connections the CLI opens on behalf of a job."""

import os
from collections.abc import Mapping

from uipath.platform.constants import ENV_UIPATH_ACCESS_TOKEN


def with_current_access_token(headers: Mapping[str, str]) -> dict[str, str]:
    """A copy of ``headers`` whose ``Authorization`` carries the token now in the environment.

    A long job's runtime renews the token in the environment, so a connection opened late
    in the job must send the renewed token, not the one read when the headers were built.
    Only an ``Authorization`` header that is already present is replaced, and only when the
    variable is set.
    """
    result = dict(headers)
    token = os.environ.get(ENV_UIPATH_ACCESS_TOKEN)
    if token and "Authorization" in result:
        result["Authorization"] = f"Bearer {token}"
    return result
