from typing import Dict, cast

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import UserAsset
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class AssetsService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def retrieve(
        self,
        asset_name: str,
    ) -> str:
        spec = self._retrieve_spec(asset_name)

        # TODO: by types
        return cast(
            UserAsset,
            self.request(spec.method, url=spec.endpoint, content=spec.content).json(),
        )["CredentialPassword"]

    async def retrieve_async(
        self,
        asset_name: str,
    ) -> str:
        spec = self._retrieve_spec(asset_name)

        # TODO: by types
        return cast(
            UserAsset,
            (
                await self.request_async(
                    spec.method, url=spec.endpoint, content=spec.content
                )
            ).json(),
        )["CredentialPassword"]

    def update(
        self,
        robot_asset: UserAsset,
    ) -> Response:
        spec = self._update_spec(robot_asset)

        return self.request(spec.method, url=spec.endpoint, content=spec.content)

    async def update_async(
        self,
        robot_asset: UserAsset,
    ) -> Response:
        spec = self._update_spec(robot_asset)

        return await self.request_async(
            spec.method, url=spec.endpoint, content=spec.content
        )

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _retrieve_spec(self, asset_name: str) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
            ),
            content=str(
                {"assetName": asset_name, "robotKey": self._execution_context.robot_key}
            ),
        )

    def _update_spec(self, robot_asset: UserAsset) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey"
            ),
            content=str(
                {
                    "robotKey": self._execution_context.robot_key,
                    "robotAsset": robot_asset,
                }
            ),
        )
