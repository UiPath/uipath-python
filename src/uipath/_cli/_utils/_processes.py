import json
import urllib.parse
from typing import Any, Optional

import click
import requests

from ..spinner import Spinner


def get_release_info(
    base_url: str,
    token: str,
    package_name: str,
    folder_id: str,
    spinner: Optional[Spinner] = None,
) -> None | tuple[Any, Any] | tuple[None, None]:
    headers = {
        "Authorization": f"Bearer {token}",
        "x-uipath-organizationunitid": str(folder_id),
    }

    release_url = f"{base_url}/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases?$select=Id,Key&$top=1&$filter=(contains(Name,%27{urllib.parse.quote(package_name)}%27))&$orderby=Name%20asc"
    response = requests.get(release_url, headers=headers)
    if response.status_code == 200:
        try:
            data = json.loads(response.text)
            release_id = data["value"][0]["Id"]
            release_key = data["value"][0]["Key"]
            return release_id, release_key
        except KeyError:
            if spinner:
                spinner.stop()
            click.echo("\n⚠️ Warning: Failed to deserialize release data")
            return None, None
        except IndexError:
            if spinner:
                spinner.stop()
            click.echo(
                "\n❌ Process not found in your workspace. Try publishing it first."
            )
            click.get_current_context().exit(1)

    else:
        if spinner:
            spinner.stop()
        click.echo("\n⚠️ Warning: Failed to fetch release info")
        click.echo(f"Status code: {response.status_code}")
        return None, None
