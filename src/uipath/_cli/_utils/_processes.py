import json
import urllib.parse
from typing import Any

import httpx

from ._console import ConsoleLogger

console = ConsoleLogger()
client = httpx.Client(follow_redirects=True)


def get_release_info(
    base_url: str, token: str, package_name: str, folder_id: str
) -> None | tuple[Any, Any] | tuple[None, None]:
    headers = {
        "Authorization": f"Bearer {token}",
        "x-uipath-organizationunitid": str(folder_id),
    }

    release_url = f"{base_url}/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases?$select=Id,Key&$top=1&$filter=Name%20eq%20%27{urllib.parse.quote(package_name)}%27"
    response = client.get(release_url, headers=headers)
    if response.status_code == 200:
        try:
            data = json.loads(response.text)
            release_id = data["value"][0]["Id"]
            release_key = data["value"][0]["Key"]
            return release_id, release_key
        except KeyError:
            console.warning("Warning: Failed to deserialize release data")
            return None, None
        except IndexError:
            console.error(
                f"Error: No process with name '{package_name}' found in your workspace. Please publish the process first."
            )
            return None, None
    else:
        console.warning(f"Warning: Failed to fetch release info {response.status_code}")
        return None, None
