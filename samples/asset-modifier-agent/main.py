import dataclasses
import dotenv
import logging
import os

from typing import Optional
from uipath import UiPath
from uipath.tracing import traced

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

def get_uipath_client() -> UiPath:
    """Initialize and return a UiPath client using environment variables.

    Returns:
        UiPath: An instance of the UiPath client.
    """
    UIPATH_CLIENT_ID = "EXTERNAL_APP_CLIENT_ID_HERE"
    UIPATH_CLIENT_SECRET = os.getenv("UIPATH_CLIENT_SECRET")
    UIPATH_SCOPE = "OR.Assets"
    UIPATH_URL = "base_url"
    return UiPath(
        client_id=UIPATH_CLIENT_ID,
        client_secret=UIPATH_CLIENT_SECRET,
        scope=UIPATH_SCOPE,
        base_url=UIPATH_URL
    )

@dataclasses.dataclass
class AgentInput:
    """Input data structure for the UiPath agent.

    Attributes:
        asset_name (str): The name of the UiPath asset.
        folder_path (str): The folder path where the asset is located.
    """
    asset_name: str
    folder_path: str

def get_asset(client: UiPath, name: str, folder_path: str) -> Optional[object]:
    """Retrieve an asset from UiPath.

    Args:
        name (str): The asset name.
        folder_path (str): The UiPath folder path.

    Returns:
        Optional[object]: The asset object if found, else None.
    """
    return client.assets.retrieve(name=name, folder_path=folder_path)

def check_asset(asset: object) -> str:
    """Check if an asset's IntValue is within a valid range.

    Args:
        asset (object): The asset object.

    Returns:
        str: Result message depending on asset state.
    """
    if asset is None:
        return "Asset not found."

    int_value = getattr(asset, "int_value", None)
    if int_value is None:
        return "Asset does not have an IntValue."

    if 100 <= int_value <= 1000:
        return f"Asset '{asset.name}' has a valid IntValue: {int_value}"
    else:
        return f"Asset '{asset.name}' has an out-of-range IntValue: {int_value}"

@traced()
def main(input: AgentInput) -> str:
    """Main entry point for the agent.

    Args:
        input (AgentInput): The input containing asset details.

    Returns:
        str: Message with the result of the asset check.
    """
    client = get_uipath_client()
    asset = get_asset(client, input.asset_name, input.folder_path)
    return check_asset(asset)
