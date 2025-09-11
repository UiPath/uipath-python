from uipath import UiPath
from uipath.tracing import traced
import dotenv
import logging
import os
import sys

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

uipath = UiPath(
    client_id=os.getenv("UIPATH_CLIENT_ID"),
    client_secret=os.getenv("UIPATH_CLIENT_SECRET"),
    scope=os.getenv("SCOPE"),
)

def get_asset(name, folder_path):
    return uipath.assets.retrieve(name=name, folder_path=folder_path)

def update_fields(asset, value: int, description: str):
    asset.IntValue = value
    asset.Value = str(value)
    asset.Description = description
    return asset

@traced()
def main(asset_name: str, folder_path: str):
    asset = get_asset(asset_name, folder_path)
    updated_asset = update_fields(asset, 919, "Updated from external app")
    uipath.assets.update(asset=updated_asset, folder_path=folder_path)

if __name__ == "__main__":
    asset_name = sys.argv[1] if len(sys.argv) > 1 else "test-asset"
    folder_path = sys.argv[2] if len(sys.argv) > 2 else "Shared"
    main(asset_name, folder_path)
