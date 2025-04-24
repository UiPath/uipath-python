from typing import Optional, Tuple

import click
import requests

from ..spinner import Spinner


def get_personal_workspace_info(
    base_url: str, token: str, spinner: Optional[Spinner] = None
) -> Tuple[str, str]:
    user_url = f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended?$expand=PersonalWorkspace"
    user_response = requests.get(user_url, headers={"Authorization": f"Bearer {token}"})

    if user_response.status_code != 200:
        if spinner:
            spinner.stop()
        click.echo("❌ Failed to get user info. Please try reauthenticating.")
        click.get_current_context().exit(1)

    user_data = user_response.json()
    feed_id = user_data.get("PersonalWorskpaceFeedId")
    folder_id = user_data["PersonalWorkspace"].get("Id")
    if not (feed_id and folder_id):
        if spinner:
            spinner.stop()
        click.echo("❌ No personal workspace found for user")
        click.get_current_context().exit(1)
    return feed_id, folder_id
