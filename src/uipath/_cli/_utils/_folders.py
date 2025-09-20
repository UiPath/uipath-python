from typing import Any, Optional, Tuple

from ._console import ConsoleLogger

console = ConsoleLogger()


async def get_personal_workspace_info_async() -> Tuple[Optional[str], Optional[str]]:
    response = await _get_personal_workspace_info_internal_async()
    feed_id = response.get("PersonalWorskpaceFeedId")
    personal_workspace = response.get("PersonalWorkspace")

    if not personal_workspace or not feed_id or "Id" not in personal_workspace:
        return None, None

    folder_id = personal_workspace.get("Id")
    return feed_id, folder_id


async def get_personal_workspace_key_async() -> Optional[str]:
    response = await _get_personal_workspace_info_internal_async()
    personal_workspace = response.get("PersonalWorkspace")
    if not personal_workspace or "Key" not in personal_workspace:
        return None
    return personal_workspace["Key"]


async def _get_personal_workspace_info_internal_async() -> dict[str, Any]:
    from ... import UiPath

    uipath = UiPath()

    response = await uipath.api_client.request_async(
        method="GET",
        url="/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended?$expand=PersonalWorkspace",
    )

    if response.status_code != 200:
        console.error("Error: Failed to fetch user info. Please try reauthenticating.")

    return response.json()
