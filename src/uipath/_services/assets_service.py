from typing import Dict, Optional

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, infer_bindings
from ..models import UserAsset
from ..tracing._traced import traced
from ._base_service import BaseService


class AssetsService(FolderContext, BaseService):
    """Service for managing UiPath assets.

    Assets are key-value pairs that can be used to store configuration data,
    credentials, and other settings used by automation processes.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @infer_bindings()
    @traced(
        name="assets_retrieve", run_type="uipath", hide_input=True, hide_output=True
    )
    def retrieve(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> UserAsset:
        """Retrieve an asset by its name.

        Related Activity: [Get Asset](https://docs.uipath.com/activities/other/latest/workflow/get-robot-asset)

        Args:
            name (str): The name of the asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
           UserAsset: The asset data.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            client.assets.retrieve(name="MyAsset")
            ```
        """
        spec = self._retrieve_spec(name, folder_key=folder_key, folder_path=folder_path)
        response = self.request(
            spec.method, url=spec.endpoint, content=spec.content, headers=spec.headers
        )

        return UserAsset.model_validate(response.json())

    @traced(
        name="assets_retrieve", run_type="uipath", hide_input=True, hide_output=True
    )
    async def retrieve_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> UserAsset:
        """Asynchronously retrieve an asset by its name.

        Related Activity: [Get Asset](https://docs.uipath.com/activities/other/latest/workflow/get-robot-asset)

        Args:
            name (str): The name of the asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            UserAsset: The asset data.
        """
        spec = self._retrieve_spec(name, folder_key=folder_key, folder_path=folder_path)
        response = await self.request_async(
            spec.method, url=spec.endpoint, content=spec.content, headers=spec.headers
        )

        return UserAsset.model_validate(response.json())

    @infer_bindings()
    @traced(
        name="assets_credential", run_type="uipath", hide_input=True, hide_output=True
    )
    def retrieve_credential(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Optional[str]:
        """Gets a specified Orchestrator credential.

        The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable)

        Related Activity: [Get Credential](https://docs.uipath.com/activities/other/latest/workflow/get-robot-credential)

        Args:
            name (str): The name of the credential asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Optional[str]: The decrypted credential password.
        """
        spec = self._retrieve_spec(name, folder_key=folder_key, folder_path=folder_path)

        response = self.request(
            spec.method,
            url=spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        user_asset = UserAsset.model_validate(response.json())

        return user_asset.credential_password

    @infer_bindings()
    @traced(
        name="assets_credential", run_type="uipath", hide_input=True, hide_output=True
    )
    async def retrieve_credential_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Optional[str]:
        """Asynchronously gets a specified Orchestrator credential.

        The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable)

        Related Activity: [Get Credential](https://docs.uipath.com/activities/other/latest/workflow/get-robot-credential)

        Args:
            name (str): The name of the credential asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Optional[str]: The decrypted credential password.

        """
        spec = self._retrieve_spec(name, folder_key=folder_key, folder_path=folder_path)

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        user_asset = UserAsset.model_validate(response.json())

        return user_asset.credential_password

    @traced(name="assets_update", run_type="uipath", hide_input=True, hide_output=True)
    def update(
        self,
        robot_asset: UserAsset,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Update an asset's value.

        Related Activity: [Set Asset](https://docs.uipath.com/activities/other/latest/workflow/set-asset)

        Args:
            robot_asset (UserAsset): The asset object containing the updated values.

        Returns:
            Response: The HTTP response confirming the update.
        """
        spec = self._update_spec(
            robot_asset, folder_key=folder_key, folder_path=folder_path
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        return response.json()

    @traced(name="assets_update", run_type="uipath", hide_input=True, hide_output=True)
    async def update_async(
        self,
        robot_asset: UserAsset,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """Asynchronously update an asset's value.

        Related Activity: [Set Asset](https://docs.uipath.com/activities/other/latest/workflow/set-asset)

        Args:
            robot_asset (UserAsset): The asset object containing the updated values.

        Returns:
            Response: The HTTP response confirming the update.
        """
        spec = self._update_spec(
            robot_asset, folder_key=folder_key, folder_path=folder_path
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        return response.json()

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _retrieve_spec(
        self,
        name: str,
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
                {"assetName": name, "robotKey": self._execution_context.robot_key}
            ),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _update_spec(
        self,
        robot_asset: UserAsset,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
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
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
