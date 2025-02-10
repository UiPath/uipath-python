from typing import cast

from httpx import Response

from .._folder_context import FolderContext
from .._models import UserAsset
from ._base_service import BaseService


class AssetsService(BaseService, FolderContext):
    def retrieve(
        self,
        assetName: str,
    ) -> UserAsset:
        endpoint = "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
        content = str(
            {
                "assetName": assetName,
                "robotKey": self._execution_context.robot_key,
                "supportsCredentialsProxyDisconnected": True,
            }
        )

        return cast(
            UserAsset,
            self.request(
                "POST",
                endpoint,
                content=content,
            ).json(),
        )

    def update(
        self,
        robotAsset: UserAsset,
    ) -> Response:
        endpoint = "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey"
        content = str(
            {
                "robotKey": self._execution_context.robot_key,
                "robotAsset": robotAsset,
            }
        )

        return self.request(
            "POST",
            endpoint,
            content=content,
        )

    @property
    def custom_headers(self) -> dict[str, str]:
       return self.folder_headers
