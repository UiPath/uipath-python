from typing import Any, AsyncIterator, Dict, Iterator, Optional, Union

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, resource_override
from ..models import Asset, UserAsset
from ..models.errors import PaginationLimitError
from ..tracing._traced import traced
from ._base_service import BaseService


class AssetsService(FolderContext, BaseService):
    """Service for managing UiPath assets.

    Assets are key-value pairs that can be used to store configuration data,
    credentials, and other settings used by automation processes.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._base_url = "assets"

    @traced(
        name="assets_retrieve", run_type="uipath", hide_input=True, hide_output=True
    )
    @resource_override(resource_type="asset")
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
            from uipath import UiPath

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
            items = response.json().get("value", [])
            if not items:
                raise LookupError(f"Asset with name '{name}' not found.")
            return Asset.model_validate(items[0])

    @traced(
        name="assets_retrieve", run_type="uipath", hide_input=True, hide_output=True
    )
    @resource_override(resource_type="asset")
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
            items = response.json().get("value", [])
            if not items:
                raise LookupError(f"Asset with name '{name}' not found.")
            return Asset.model_validate(items[0])

    @traced(
        name="assets_credential", run_type="uipath", hide_input=True, hide_output=True
    )
    @resource_override(resource_type="asset")
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

        Raises:
            ValueError: If the method is called for a user asset.
        """
        try:
            is_user = self._execution_context.robot_key is not None
        except ValueError:
            is_user = False

        if not is_user:
            raise ValueError("This method can only be used for robot assets.")

        spec = self._retrieve_spec(
            name,
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

        user_asset = UserAsset.model_validate(response.json())

        return user_asset.credential_password

    @traced(
        name="assets_credential", run_type="uipath", hide_input=True, hide_output=True
    )
    @resource_override(resource_type="asset")
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

        Raises:
            ValueError: If the method is called for a user asset.
        """
        try:
            is_user = self._execution_context.robot_key is not None
        except ValueError:
            is_user = False

        if not is_user:
            raise ValueError("This method can only be used for robot assets.")

        spec = self._retrieve_spec(
            name,
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

    @traced(name="assets_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> Iterator[Asset]:
        """List assets with automatic pagination (limited to 10 pages).

        Args:
            folder_path: Folder path to filter assets
            folder_key: Folder key (mutually exclusive with folder_path)
            name: Filter by asset name (contains match)
            filter: OData $filter expression
            orderby: OData $orderby expression
            top: Maximum items per page (default 100)
            skip: Number of items to skip

        Yields:
            Asset: Asset resource instances

        Raises:
            PaginationLimitError: If more than 10 pages (1,000 items) exist.
                Use filters or manual pagination to retrieve additional results.

        Note:
            Auto-pagination is limited to 10 pages (~1,000 items) to prevent
            performance issues with deep OFFSET queries. If you hit this limit:

            1. Add filters to narrow results:
               >>> for asset in sdk.assets.list(filter="ValueType eq 'Text'"):
               ...     print(asset.name)

        Examples:
            >>> # List all assets (up to 1,000)
            >>> for asset in sdk.assets.list():
            ...     print(asset.name, asset.value)
            >>>
            >>> # Filter by name
            >>> for asset in sdk.assets.list(name="API"):
            ...     print(asset.name)
        """
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_spec(
                folder_path=folder_path,
                folder_key=folder_key,
                name=name,
                filter=filter,
                orderby=orderby,
                skip=current_skip,
                top=top,
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                asset = Asset.model_validate(item)
                yield asset

            pages_fetched += 1

            if len(items) < top:
                break

            current_skip += top

        else:
            if items and len(items) == top:
                raise PaginationLimitError.create(
                    max_pages=MAX_PAGES,
                    items_per_page=top,
                    method_name="list",
                    current_skip=current_skip,
                    filter_example="ValueType eq 'Text'",
                )

    @traced(name="assets_list", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> AsyncIterator[Asset]:
        """Async version of list() with pagination limit.

        See list() for full documentation.
        """
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_spec(
                folder_path=folder_path,
                folder_key=folder_key,
                name=name,
                filter=filter,
                orderby=orderby,
                skip=current_skip,
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
            if not items:
                break

            for item in items:
                asset = Asset.model_validate(item)
                yield asset

            pages_fetched += 1

            if len(items) < top:
                break

            current_skip += top

        else:
            if items and len(items) == top:
                raise PaginationLimitError.create(
                    max_pages=MAX_PAGES,
                    items_per_page=top,
                    method_name="list_async",
                    current_skip=current_skip,
                    filter_example="ValueType eq 'Text'",
                )

    @traced(name="assets_create", run_type="uipath")
    def create(
        self,
        *,
        name: str,
        value: Union[str, int, bool, Dict[str, Any]],
        value_type: str,
        description: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Asset:
        """Create a new asset.

        Args:
            name: Asset name (must be unique within folder)
            value: Asset value
            value_type: Type of asset ("Text", "Integer", "Boolean", "Credential", "Secret")
                - Text: Plain text values
                - Integer: Numeric values
                - Boolean: True/False values
                - Credential: Username/password pairs (robot-context only)
                - Secret: Encrypted single values like API keys (robot-context only)
            description: Optional description
            folder_path: Folder to create asset in
            folder_key: Folder key

        Returns:
            Asset: Newly created asset

        Examples:
            >>> asset = sdk.assets.create(
            ...     name="API_Key",
            ...     value="secret123",
            ...     value_type="Text"
            ... )
        """
        spec = self._create_spec(
            name=name,
            value=value,
            value_type=value_type,
            description=description,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        ).json()

        return Asset.model_validate(response)

    @traced(name="assets_create", run_type="uipath")
    async def create_async(
        self,
        *,
        name: str,
        value: Union[str, int, bool, Dict[str, Any]],
        value_type: str,
        description: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Asset:
        """Async version of create().

        Args:
            name: Asset name (must be unique within folder)
            value: Asset value
            value_type: Type of asset ("Text", "Integer", "Boolean", "Credential", "Secret")
                - Text: Plain text values
                - Integer: Numeric values
                - Boolean: True/False values
                - Credential: Username/password pairs (robot-context only)
                - Secret: Encrypted single values like API keys (robot-context only)
            description: Optional description
            folder_path: Folder to create asset in
            folder_key: Folder key

        Returns:
            Asset: Newly created asset
        """
        spec = self._create_spec(
            name=name,
            value=value,
            value_type=value_type,
            description=description,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
        ).json()

        return Asset.model_validate(response)

    @traced(name="assets_delete", run_type="uipath")
    @resource_override(resource_type="asset")
    def delete(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete an asset.

        Args:
            name: Asset name
            key: Asset key (UUID)
            folder_path: Folder path
            folder_key: Folder key

        Returns:
            None

        Examples:
            >>> sdk.assets.delete(name="OldAsset")
        """
        if not name and not key:
            raise ValueError("Either 'name' or 'key' must be provided")

        if name and not key:
            asset = self.retrieve(
                name=name, folder_path=folder_path, folder_key=folder_key
            )
            if isinstance(asset, Asset):
                key = asset.key
            else:
                raise ValueError("Cannot delete user assets via API")

        if not key:
            raise ValueError(
                f"Asset '{name}' was found, but it does not have a key and cannot be deleted."
            )

        spec = self._delete_spec(
            asset_key=key,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        self.request(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="assets_delete", run_type="uipath")
    @resource_override(resource_type="asset")
    async def delete_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Async version of delete()."""
        if not name and not key:
            raise ValueError("Either 'name' or 'key' must be provided")

        if name and not key:
            asset = await self.retrieve_async(
                name=name, folder_path=folder_path, folder_key=folder_key
            )
            if isinstance(asset, Asset):
                key = asset.key
            else:
                raise ValueError("Cannot delete user assets via API")

        if not key:
            raise ValueError(
                f"Asset '{name}' was found, but it does not have a key and cannot be deleted."
            )

        spec = self._delete_spec(
            asset_key=key,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        await self.request_async(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="assets_exists", run_type="uipath")
    def exists(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Check if asset exists.

        Args:
            name: Asset name
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            bool: True if asset exists

        Examples:
            >>> if sdk.assets.exists("API_Key"):
            ...     print("Asset found")
        """
        try:
            self.retrieve(name=name, folder_key=folder_key, folder_path=folder_path)
            return True
        except LookupError:
            return False

    @traced(name="assets_exists", run_type="uipath")
    async def exists_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Async version of exists()."""
        try:
            await self.retrieve_async(
                name=name, folder_key=folder_key, folder_path=folder_path
            )
            return True
        except LookupError:
            return False

    @traced(name="assets_get_value", run_type="uipath", hide_output=True)
    def get_value(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Union[str, int, bool, Dict[str, Any]]:
        """Get the value of an asset (convenience method).

        Args:
            name: Asset name
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            The asset value (type depends on ValueType)

        Examples:
            >>> api_key = sdk.assets.get_value("API_Key")
            >>> db_port = sdk.assets.get_value("DB_Port")  # Returns int
        """
        asset = self.retrieve(name=name, folder_key=folder_key, folder_path=folder_path)
        return asset.value

    @traced(name="assets_get_value", run_type="uipath", hide_output=True)
    async def get_value_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Union[str, int, bool, Dict[str, Any]]:
        """Async version of get_value()."""
        asset = await self.retrieve_async(
            name=name, folder_key=folder_key, folder_path=folder_path
        )
        return asset.value

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
            json={"assetName": name, "robotKey": robot_key},
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
        name: Optional[str],
        filter: Optional[str],
        orderby: Optional[str],
        skip: int,
        top: int,
    ) -> RequestSpec:
        """Build OData request for listing assets."""
        filters = []
        if name:
            escaped_name = name.replace("'", "''")
            filters.append(f"contains(tolower(Name), tolower('{escaped_name}'))")
        if filter:
            filters.append(filter)

        filter_str = " and ".join(filters) if filters else None

        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if filter_str:
            params["$filter"] = filter_str
        if orderby:
            params["$orderby"] = orderby

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Assets"),
            params=params,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _create_spec(
        self,
        name: str,
        value: Union[str, int, bool, Dict[str, Any]],
        value_type: str,
        description: Optional[str],
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        """Build request for creating asset."""
        body: Dict[str, Any] = {
            "Name": name,
            "ValueType": value_type,
        }

        if value_type == "Text":
            if isinstance(value, dict):
                raise ValueError("Text assets cannot have dict values")
            body["StringValue"] = str(value)
        elif value_type == "Integer":
            if isinstance(value, dict):
                raise ValueError("Integer assets cannot have dict values")
            body["IntValue"] = int(value) if not isinstance(value, int) else value
        elif value_type == "Boolean" or value_type == "Bool":
            if isinstance(value, dict):
                raise ValueError("Boolean assets cannot have dict values")
            body["BoolValue"] = bool(value) if not isinstance(value, bool) else value
        else:
            body["Value"] = value

        if description:
            body["Description"] = description

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/orchestrator_/odata/Assets"),
            json=body,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _delete_spec(
        self,
        asset_key: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        """Build request for deleting asset by key (UUID)."""
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"/orchestrator_/odata/Assets('{asset_key}')"),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
