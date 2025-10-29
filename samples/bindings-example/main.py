"""Sample demonstrating the use of UiPath bindings.

This example shows how to use the Bindings class to retrieve assets
and invoke processes using binding keys configured in uipath.json.
"""

import asyncio
from pydantic.dataclasses import dataclass

from uipath import UiPath, Bindings


@dataclass
class Input:
    """Input for the example."""
    message: str


@dataclass
class Output:
    """Output from the example."""
    status: str
    asset_value: str


async def main(input: Input) -> Output:
    """Main function demonstrating bindings usage.

    Before running this example:
    1. Run `uipath init` to create uipath.json
    2. Create bindings using the CLI:
       - uipath bindings create my-config-asset -t asset -n "MyConfigurationAsset"
       - uipath bindings create my-process -t process -n "MyProcessName" -f "/Shared/Folder"
    3. Set environment variables:
       - export UIPATH_URL="https://cloud.uipath.com/org/tenant"
       - export UIPATH_ACCESS_TOKEN="your_token"
       - export UIPATH_FOLDER_PATH="/your/folder"

    Args:
        input: The input containing a message

    Returns:
        Output containing status and asset value
    """
    # Initialize the UiPath SDK client
    client = UiPath()

    # Example 1: Get asset name from bindings
    # Instead of hardcoding the asset name, we use the binding key
    try:
        asset_name = Bindings.get("my-config-asset", resource_type="asset")
        print(f"Retrieving asset: {asset_name}")

        asset = client.assets.retrieve(name=asset_name)
        print(f"Asset value: {asset.value}")
        asset_value = asset.value
    except KeyError as e:
        print(f"Warning: {e}")
        asset_value = "No binding configured"

    # Example 2: Get asset with folder path from bindings
    try:
        asset_name, folder_path = Bindings.get_with_folder(
            "my-config-asset",
            resource_type="asset"
        )
        print(f"Asset: {asset_name}, Folder: {folder_path}")

        # Use the folder path if provided
        if folder_path:
            asset = client.assets.retrieve(name=asset_name, folder_path=folder_path)
        else:
            asset = client.assets.retrieve(name=asset_name)
    except KeyError:
        print("Asset binding not found, skipping...")

    # Example 3: Invoke a process using bindings
    try:
        process_name, folder_path = Bindings.get_with_folder(
            "my-process",
            resource_type="process"
        )
        print(f"Invoking process: {process_name}")

        job = client.processes.invoke(
            name=process_name,
            input_arguments={"message": input.message},
            folder_path=folder_path
        )
        print(f"Job started with ID: {job.key}")
    except KeyError:
        print("Process binding not found, skipping...")

    # Example 4: Using default values
    # If a binding doesn't exist, you can provide a default
    asset_name = Bindings.get(
        "optional-asset",
        resource_type="asset",
        default="DefaultAssetName"
    )
    print(f"Asset name (with default): {asset_name}")

    return Output(
        status="success",
        asset_value=asset_value
    )


if __name__ == "__main__":
    # For testing locally
    test_input = Input(message="Hello from bindings example!")
    result = asyncio.run(main(test_input))
    print(f"Result: {result}")
