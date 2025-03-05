from typing import Dict, Optional, cast

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import UserAsset
from .._utils import Endpoint, RequestSpec, header_folder
from ._base_service import BaseService


class AssetsService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def retrieve(
        self,
        key: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        spec = self._retrieve_spec(key, folder_key=folder_key, folder_path=folder_path)
        return self.request(
            spec.method, url=spec.endpoint, content=spec.content, headers=spec.headers
        )

    async def retrieve_async(
        self,
        key: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        spec = self._retrieve_spec(key, folder_key=folder_key, folder_path=folder_path)
        return await self.request_async(
            spec.method, url=spec.endpoint, content=spec.content, headers=spec.headers
        )

    def retrieve_credential(
        self,
        asset_name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> str:
        spec = self._retrieve_credential_spec(
            asset_name, folder_key=folder_key, folder_path=folder_path
        )

        return cast(
            UserAsset,
            self.request(
                spec.method,
                url=spec.endpoint,
                content=spec.content,
                headers=spec.headers,
            ).json(),
        )["CredentialPassword"]

    async def retrieve_credential_async(
        self,
        asset_name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> str:
        spec = self._retrieve_credential_spec(
            asset_name, folder_key=folder_key, folder_path=folder_path
        )

        return cast(
            UserAsset,
            (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    content=spec.content,
                    headers=spec.headers,
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

    def _retrieve_spec(
        self,
        key: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/orchestrator_/odata/Assets({key})"),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_credential_spec(
        self,
        asset_name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
            ),
            content=str(
                {"assetName": asset_name, "robotKey": self._execution_context.robot_key}
            ),
            headers={
                **header_folder(folder_key, folder_path),
            },
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
