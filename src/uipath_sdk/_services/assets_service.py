from typing import cast

from httpx import Response

from .._models import UserAsset
from ._base_service import BaseService


class RobotAssetsService(BaseService):
    def retrieve(
        self,
        assetName: str,
        robotKey: str,
    ) -> UserAsset:
        endpoint = "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
        content = str(
            {
                "assetName": assetName,
                "robotKey": robotKey,
                "supportsCredentialsProxyDisconnected": True,
            }
        )

        return cast(
            UserAsset,
            self.client.post(
                endpoint,
                content=content,
            ).json(),
        )

    def update(
        self,
        robotKey: str,
        robotAsset: UserAsset,
    ) -> Response:
        endpoint = "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey"
        content = str(
            {
                "robotKey": robotKey,
                "robotAsset": robotAsset,
            }
        )

        return self.client.post(
            endpoint,
            content=content,
        )
