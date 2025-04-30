from typing import Optional, Tuple

import httpx

from ._console import ConsoleLogger

console = ConsoleLogger()
client = httpx.Client(follow_redirects=True)


def get_personal_workspace_info(
    base_url: str, token: str
) -> Tuple[Optional[str], Optional[str]]:
    user_url = f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended?$expand=PersonalWorkspace"
    user_response = client.get(user_url, headers={"Authorization": f"Bearer {token}"})

    if user_response.status_code != 200:
        console.error("Error: Failed to fetch user info. Please try reauthenticating.")

    user_data = user_response.json()
    feed_id = user_data.get("PersonalWorskpaceFeedId")
    personal_workspace = user_data.get("PersonalWorkspace")

    if not personal_workspace or not feed_id or "Id" not in personal_workspace:
        return None, None

    folder_id = personal_workspace.get("Id")
    return feed_id, folder_id
