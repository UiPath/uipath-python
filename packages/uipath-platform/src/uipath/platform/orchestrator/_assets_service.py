from typing import Any, Dict, Optional

from httpx import Response
from uipath.core import traced

from ..common._base_service import BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from ..common.paging import PagedResult
from ..common.validation import validate_pagination_params
from .assets import Asset, UserAsset


class AssetsService(FolderContext, BaseService):
    """Service for managing UiPath assets.

    Assets are key-value pairs that can be used to store configuration data,
    credentials, and other settings used by automation processes.
    """

    # Pagination limits
    MAX_PAGE_SIZE = 1000  # Maximum items per page
    MAX_SKIP_OFFSET = 10000  # Maximum skip offset

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._base_url = "assets"

    @traced(name="assets_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[Asset]:
        """List assets using OData API with offset-based pagination.

        Returns a single page of results with pagination metadata.

        Args:
            folder_path: Folder path to filter assets.
            folder_key: Folder key (mutually exclusive with folder_path).
            filter: OData $filter expression (e.g., "ValueType eq 'Text'").
            orderby: OData $orderby expression (e.g., "Name asc").
            skip: Number of items to skip (default 0, max 10000).
            top: Maximum items per page (default 100, max 1000).

        Returns:
            PagedResult[Asset]: Page of assets with pagination metadata.

        Raises:
            ValueError: If skip or top parameters are invalid.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()

            # List all assets in the default folder
            result = client.assets.list(top=100)
            for asset in result.items:
                print(asset.name, asset.value_type)

            # List with filter
            result = client.assets.list(filter="ValueType eq 'Text'")

            # Paginate through all assets
            skip = 0
            while True:
                result = client.assets.list(skip=skip, top=100)
                for asset in result.items:
                    print(asset.name)
                if not result.has_more:
                    break
                skip += 100
            ```
        """
        validate_pagination_params(
            skip=skip,
            top=top,
            max_skip=self.MAX_SKIP_OFFSET,
            max_top=self.MAX_PAGE_SIZE,
        )

        spec = self._list_spec(
            folder_path=folder_path,
            folder_key=folder_key,
            filter=filter,
            orderby=orderby,
            skip=skip,
            top=top,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()

        items = response.get("value", [])
        assets = [Asset.model_validate(item) for item in items]

        return PagedResult(
            items=assets,
            has_more=len(items) == top,
            skip=skip,
            top=top,
        )

    @traced(name="assets_list", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[Asset]:
        """Asynchronously list assets using OData API with offset-based pagination.

        Returns a single page of results with pagination metadata.

        Args:
            folder_path: Folder path to filter assets.
            folder_key: Folder key (mutually exclusive with folder_path).
            filter: OData $filter expression (e.g., "ValueType eq 'Text'").
            orderby: OData $orderby expression (e.g., "Name asc").
            skip: Number of items to skip (default 0, max 10000).
            top: Maximum items per page (default 100, max 1000).

        Returns:
            PagedResult[Asset]: Page of assets with pagination metadata.

        Raises:
            ValueError: If skip or top parameters are invalid.
        """
        validate_pagination_params(
            skip=skip,
            top=top,
            max_skip=self.MAX_SKIP_OFFSET,
            max_top=self.MAX_PAGE_SIZE,
        )

        spec = self._list_spec(
            folder_path=folder_path,
            folder_key=folder_key,
            filter=filter,
            orderby=orderby,
            skip=skip,
            top=top,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()

        items = response.get("value", [])
        assets = [Asset.model_validate(item) for item in items]

        return PagedResult(
            items=assets,
            has_more=len(items) == top,
            skip=skip,
            top=top,
        )

    @resource_override(resource_type="asset")
    @traced(
        name="assets_retrieve", run_type="uipath", hide_input=True, hide_output=True
    )
    def retrieve(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> UserAsset | Asset:
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
            from uipath.platform import UiPath

            client = UiPath()

            client.assets.retrieve(name="MyAsset")
            ```
        """
        try:
            is_user = self._execution_context.robot_key is not None
        except ValueError:
            is_user = False

        spec = self._retrieve_spec(
            name,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
            json=spec.json,
        )

        if is_user:
            return UserAsset.model_validate(response.json())
        else:
            return Asset.model_validate(response.json()["value"][0])

    @resource_override(resource_type="asset")
    @traced(
        name="assets_retrieve", run_type="uipath", hide_input=True, hide_output=True
    )
    async def retrieve_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> UserAsset | Asset:
        """Asynchronously retrieve an asset by its name.

        Related Activity: [Get Asset](https://docs.uipath.com/activities/other/latest/workflow/get-robot-asset)

        Args:
            name (str): The name of the asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            UserAsset: The asset data.
        """
        try:
            is_user = self._execution_context.robot_key is not None
        except ValueError:
            is_user = False

        spec = self._retrieve_spec(
            name,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
            json=spec.json,
        )

        if is_user:
            return UserAsset.model_validate(response.json())
        else:
            return Asset.model_validate(response.json()["value"][0])

    def _resolve_robot_key(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Optional[str]:
        """Return the robot key, or ``None`` if the asset opts into direct API access.

        Raises ``ValueError`` when no robot key is available and ``AllowDirectApiAccess``
        is not enabled on the asset.
        """
        try:
            robot_key = self._execution_context.robot_key
        except ValueError:
            robot_key = None

        if robot_key is None:
            asset = self.retrieve(
                name=name, folder_key=folder_key, folder_path=folder_path
            )
            if not asset.allow_direct_api_access:
                raise ValueError(
                    f"No robot key available and 'AllowDirectApiAccess' is disabled for asset '{name}'."
                )
        return robot_key

    async def _resolve_robot_key_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Optional[str]:
        """Async variant of :meth:`_resolve_robot_key`."""
        try:
            robot_key = self._execution_context.robot_key
        except ValueError:
            robot_key = None

        if robot_key is None:
            asset = await self.retrieve_async(
                name=name, folder_key=folder_key, folder_path=folder_path
            )
            if not asset.allow_direct_api_access:
                raise ValueError(
                    f"No robot key available and 'AllowDirectApiAccess' is disabled for asset '{name}'."
                )
        return robot_key

    @resource_override(resource_type="asset")
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
        """Get the decrypted password of a Credential asset.

        The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable).
        If no robot key is available, the asset's `AllowDirectApiAccess` flag is checked: when
        enabled, the credential is fetched without a robot key; otherwise a `ValueError` is raised.

        Related Activity: [Get Credential](https://docs.uipath.com/activities/other/latest/workflow/get-robot-credential)

        Args:
            name (str): The name of the credential asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Optional[str]: The decrypted credential password.

        Raises:
            ValueError: If no robot key is available and the asset does not have `AllowDirectApiAccess` enabled.
        """
        robot_key = self._resolve_robot_key(
            name, folder_key=folder_key, folder_path=folder_path
        )

        spec = self._retrieve_credential_spec(
            name,
            robot_key=robot_key,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        return UserAsset.model_validate(response.json()).credential_password

    @resource_override(resource_type="asset")
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
        """Asynchronously get the decrypted password of a Credential asset.

        The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable).
        If no robot key is available, the asset's `AllowDirectApiAccess` flag is checked: when
        enabled, the credential is fetched without a robot key; otherwise a `ValueError` is raised.

        Related Activity: [Get Credential](https://docs.uipath.com/activities/other/latest/workflow/get-robot-credential)

        Args:
            name (str): The name of the credential asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Optional[str]: The decrypted credential password.

        Raises:
            ValueError: If no robot key is available and the asset does not have `AllowDirectApiAccess` enabled.
        """
        robot_key = await self._resolve_robot_key_async(
            name, folder_key=folder_key, folder_path=folder_path
        )

        spec = self._retrieve_credential_spec(
            name,
            robot_key=robot_key,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        return UserAsset.model_validate(response.json()).credential_password

    @resource_override(resource_type="asset")
    @traced(name="assets_secret", run_type="uipath", hide_input=True, hide_output=True)
    def retrieve_secret(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Optional[str]:
        """Get the decrypted value of a Secret asset.

        The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable).
        If no robot key is available, the asset's `AllowDirectApiAccess` flag is checked: when
        enabled, the secret is fetched without a robot key; otherwise a `ValueError` is raised.

        Args:
            name (str): The name of the secret asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Optional[str]: The decrypted secret value.

        Raises:
            ValueError: If no robot key is available and the asset does not have `AllowDirectApiAccess` enabled.
        """
        robot_key = self._resolve_robot_key(
            name, folder_key=folder_key, folder_path=folder_path
        )

        spec = self._retrieve_credential_spec(
            name,
            robot_key=robot_key,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        return UserAsset.model_validate(response.json()).secret_value

    @resource_override(resource_type="asset")
    @traced(name="assets_secret", run_type="uipath", hide_input=True, hide_output=True)
    async def retrieve_secret_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Optional[str]:
        """Asynchronously get the decrypted value of a Secret asset.

        The robot id is retrieved from the execution context (`UIPATH_ROBOT_KEY` environment variable).
        If no robot key is available, the asset's `AllowDirectApiAccess` flag is checked: when
        enabled, the secret is fetched without a robot key; otherwise a `ValueError` is raised.

        Args:
            name (str): The name of the secret asset.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Optional[str]: The decrypted secret value.

        Raises:
            ValueError: If no robot key is available and the asset does not have `AllowDirectApiAccess` enabled.
        """
        robot_key = await self._resolve_robot_key_async(
            name, folder_key=folder_key, folder_path=folder_path
        )

        spec = self._retrieve_credential_spec(
            name,
            robot_key=robot_key,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        return UserAsset.model_validate(response.json()).secret_value

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

        Raises:
            ValueError: If the method is called for a user asset.
        """
        try:
            is_user = self._execution_context.robot_key is not None
        except ValueError:
            is_user = False

        if not is_user:
            raise ValueError("This method can only be used for robot assets.")

        spec = self._update_spec(
            robot_asset, folder_key=folder_key, folder_path=folder_path
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
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
            params=spec.params,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )

        return response.json()

    @traced(name="assets_exists", run_type="uipath")
    def exists(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Check whether an asset with the given name exists.

        Args:
            name (str): The name of the asset.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            bool: True if an asset with the given name exists, False otherwise.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()

            client.assets.exists(name="MyAsset")
            ```
        """
        spec = self._list_spec(
            folder_path=folder_path,
            folder_key=folder_key,
            filter=f"Name eq '{name}'",
            orderby=None,
            skip=0,
            top=1,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
            json=spec.json,
        )
        return len(response.json().get("value", [])) > 0

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
        try:
            robot_key = self._execution_context.robot_key
        except ValueError:
            robot_key = None

        if robot_key is None:
            return RequestSpec(
                method="GET",
                endpoint=Endpoint(
                    "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered",
                ),
                params={"$filter": f"Name eq '{name}'", "$top": 1},
                headers={
                    **header_folder(folder_key, folder_path),
                },
            )

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
            ),
            json={
                "assetName": name,
                "robotKey": robot_key,
                "supportsCredentialsProxyDisconnected": True,
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_credential_spec(
        self,
        name: str,
        *,
        robot_key: Optional[str],
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        body: Dict[str, Any] = {
            "assetName": name,
            "supportsCredentialsProxyDisconnected": True,
        }
        if robot_key is not None:
            body["robotKey"] = robot_key

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetRobotAssetByNameForRobotKey"
            ),
            json=body,
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
            json={
                "robotKey": self._execution_context.robot_key,
                "robotAsset": robot_asset.model_dump(by_alias=True, exclude_none=True),
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _list_spec(
        self,
        folder_path: Optional[str],
        folder_key: Optional[str],
        filter: Optional[str],
        orderby: Optional[str],
        skip: int,
        top: int,
    ) -> RequestSpec:
        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if filter:
            params["$filter"] = filter
        if orderby:
            params["$orderby"] = orderby

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                "/orchestrator_/odata/Assets/UiPath.Server.Configuration.OData.GetFiltered"
            ),
            params=params,
            headers={**header_folder(folder_key, folder_path)},
        )
