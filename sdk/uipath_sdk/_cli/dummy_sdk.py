# type: ignore
class AssetManager:
    def __init__(self):
        self.assets = {}

    def listAssets(self):
        return list(self.assets.items())

    def retrieveAsset(self, asset_id):
        return self.assets.get(asset_id)

    def setAsset(self, asset_id, asset_value):
        self.assets[asset_id] = asset_value


AssetManager = AssetManager()
