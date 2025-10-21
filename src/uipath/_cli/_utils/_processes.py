import json
import urllib.parse
from typing import Any

import httpx

from ..._utils._ssl_context import get_httpx_client_kwargs
from ._console import ConsoleLogger

console = ConsoleLogger()
odata_top_filter = 25


def get_release_info(
    base_url: str,
    token: str,
    package_name: str,
    package_version: str,
    folder_id: str,
) -> None | tuple[Any, Any] | tuple[None, None]:
    headers = {
        "Authorization": f"Bearer {token}",
        "x-uipath-organizationunitid": str(folder_id),
    }

    release_url = f"{base_url}/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases?$select=Id,Key,ProcessVersion&$top={odata_top_filter}&$filter=ProcessKey%20eq%20%27{urllib.parse.quote(package_name)}%27"

    with httpx.Client(**get_httpx_client_kwargs()) as client:
        response = client.get(release_url, headers=headers)

        if response.status_code == 200:
            try:
                data = json.loads(response.text)
                process = next(
                    process
                    for process in data["value"]
                    if process["ProcessVersion"] == package_version
                )
                release_id = process["Id"]
                release_key = process["Key"]
                return release_id, release_key
            except KeyError:
                console.warning("Warning: Failed to deserialize release data")
                return None, None
            except StopIteration:
                console.error(
                    f"Error: No process with name '{package_name}' found in your workspace. Please publish the process first."
                )
                return None, None
        else:
            console.warning(
                f"Warning: Failed to fetch release info {response.status_code}"
            )
            return None, None
