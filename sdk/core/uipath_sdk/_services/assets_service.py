from typing import Dict, cast

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import UserAsset
from .._utils import Endpoint
from ._base_service import BaseService


class AssetsService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def retrieve(
        self,
        assetName: str,
    ) -> str:
        endpoint = Endpoint(
            "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
        )
        content = str(
            {"assetName": assetName, "robotKey": self._execution_context.robot_key}
        )

        return cast(
            UserAsset,
            self.request(
                "POST",
                endpoint,
                content=content,
            ).json(),
        )["CredentialPassword"]

    def update(
        self,
        robotAsset: UserAsset,
    ) -> Response:
        endpoint = Endpoint(
            "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.SetRobotAssetByRobotKey"
        )
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
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
