# type: ignore

import dummy_sdk as sdk

sdk.AssetManager.setAsset("asset1", "value1")
sdk.AssetManager.setAsset("asset2", 42)
sdk.AssetManager.setAsset("asset3", True)
var = "name"
sdk.AssetManager.setAsset(f"composed {var}", True)
