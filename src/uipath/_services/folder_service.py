from typing import Any, AsyncIterator, Dict, Iterator, Optional

from typing_extensions import deprecated

from uipath.tracing import traced

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint, RequestSpec
from ..models.errors import PaginationLimitError
from ..models.folders import Folder
from ._base_service import BaseService


class FolderService(BaseService):
    """Service for managing UiPath Folders.

    A folder represents a single area for data organization
    and access control - it is created when you need to categorize, manage, and enforce authorization rules for a group
    of UiPath resources (i.e. processes, assets, connections, storage buckets etc.) or other folders
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="folders_list", run_type="uipath")
    def list(
        self,
        *,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> Iterator[Folder]:
        """List folders with auto-pagination.

        Args:
            filter: OData $filter expression
            orderby: OData $orderby expression
            top: Maximum items per page (default 100)
            skip: Number of items to skip

        Yields:
            Folder: Folder instances

        Examples:
            >>> for folder in sdk.folders.list():
            ...     print(folder.display_name, folder.fully_qualified_name)
        """
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_spec(
                filter=filter,
                orderby=orderby,
                skip=current_skip,
                top=top,
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                folder = Folder.model_validate(item)
                yield folder

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
                    filter_example="ProvisionType eq 'Manual'",
                )

    @traced(name="folders_list", run_type="uipath")
    async def list_async(
        self,
        *,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: int = 100,
        skip: int = 0,
    ) -> AsyncIterator[Folder]:
        """Async version of list()."""
        MAX_PAGES = 10
        current_skip = skip
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._list_spec(
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
                )
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                folder = Folder.model_validate(item)
                yield folder

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
                    filter_example="ProvisionType eq 'Manual'",
                )

    @traced(name="folders_retrieve", run_type="uipath")
    def retrieve(
        self,
        *,
        key: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Folder:
        """Retrieve a folder by key or display name.

        Args:
            key: Folder UUID key
            display_name: Folder display name

        Returns:
            Folder: The folder

        Raises:
            LookupError: If the folder is not found

        Examples:
            >>> folder = sdk.folders.retrieve(display_name="Shared")
        """
        if not key and not display_name:
            raise ValueError("Either 'key' or 'display_name' must be provided")

        if key:
            for folder in self.list():
                if folder.key == key:
                    return folder
            raise LookupError(f"Folder with key '{key}' not found.")

        spec = self._retrieve_folder_spec(
            key=None,
            display_name=display_name,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
        ).json()

        items = response.get("value", [])
        if not items:
            raise LookupError(f"Folder with display_name '{display_name}' not found.")
        return Folder.model_validate(items[0])

    @traced(name="folders_retrieve", run_type="uipath")
    async def retrieve_async(
        self,
        *,
        key: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Folder:
        """Async version of retrieve()."""
        if not key and not display_name:
            raise ValueError("Either 'key' or 'display_name' must be provided")

        if key:
            async for folder in self.list_async():
                if folder.key == key:
                    return folder
            raise LookupError(f"Folder with key '{key}' not found.")

        spec = self._retrieve_folder_spec(
            key=None,
            display_name=display_name,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            )
        ).json()

        items = response.get("value", [])
        if not items:
            raise LookupError(f"Folder with display_name '{display_name}' not found.")
        return Folder.model_validate(items[0])

    @traced(name="folders_retrieve_by_path", run_type="uipath")
    def retrieve_by_path(self, folder_path: str) -> Folder:
        """Retrieve a folder by its fully qualified path.

        Args:
            folder_path: The fully qualified folder path (e.g., 'Shared/Finance')

        Returns:
            Folder: The folder

        Raises:
            LookupError: If the folder is not found

        Examples:
            >>> folder = sdk.folders.retrieve_by_path("Shared/Finance")
        """
        spec = self._retrieve_by_path_spec(folder_path=folder_path)
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
        ).json()

        items = response.get("value", [])
        if not items:
            raise LookupError(f"Folder with path '{folder_path}' not found.")
        return Folder.model_validate(items[0])

    @traced(name="folders_retrieve_by_path", run_type="uipath")
    async def retrieve_by_path_async(self, folder_path: str) -> Folder:
        """Async version of retrieve_by_path()."""
        spec = self._retrieve_by_path_spec(folder_path=folder_path)
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            )
        ).json()

        items = response.get("value", [])
        if not items:
            raise LookupError(f"Folder with path '{folder_path}' not found.")
        return Folder.model_validate(items[0])

    @traced(name="folders_exists", run_type="uipath")
    def exists(
        self,
        *,
        key: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> bool:
        """Check if folder exists.

        Args:
            key: Folder UUID key
            display_name: Folder display name

        Returns:
            bool: True if folder exists

        Examples:
            >>> if sdk.folders.exists(display_name="Shared"):
            ...     print("Folder found")
        """
        try:
            self.retrieve(key=key, display_name=display_name)
            return True
        except LookupError:
            return False

    @traced(name="folders_exists", run_type="uipath")
    async def exists_async(
        self,
        *,
        key: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> bool:
        """Async version of exists()."""
        try:
            await self.retrieve_async(key=key, display_name=display_name)
            return True
        except LookupError:
            return False

    @traced(name="folder_retrieve_key_by_folder_path", run_type="uipath")
    @deprecated("Use retrieve_key instead")
    def retrieve_key_by_folder_path(self, folder_path: str) -> Optional[str]:
        return self.retrieve_key(folder_path=folder_path)

    @traced(name="folder_retrieve_key", run_type="uipath")
    def retrieve_key(self, *, folder_path: str) -> Optional[str]:
        """Retrieve the folder key by folder path with pagination support.

        Args:
            folder_path: The fully qualified folder path to search for.

        Returns:
            The folder key if found, None otherwise.
        """
        MAX_PAGES = 50  # Safety limit for search (20 items/page = 1000 items max)
        skip = 0
        take = 20
        pages_fetched = 0

        while pages_fetched < MAX_PAGES:
            spec = self._retrieve_spec(folder_path, skip=skip, take=take)
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            ).json()

            folder_key = next(
                (
                    item["Key"]
                    for item in response["PageItems"]
                    if item["FullyQualifiedName"] == folder_path
                ),
                None,
            )

            if folder_key is not None:
                return folder_key

            page_items = response["PageItems"]
            pages_fetched += 1

            if len(page_items) < take:
                break

            skip += take

        else:
            if page_items and len(page_items) == take:
                raise PaginationLimitError.create(
                    max_pages=MAX_PAGES,
                    items_per_page=take,
                    method_name="retrieve_key",
                    current_skip=skip,
                    filter_example=f"folder_path='{folder_path}'",
                )

        return None

    def _retrieve_spec(
        self, folder_path: str, *, skip: int = 0, take: int = 20
    ) -> RequestSpec:
        folder_name = folder_path.split("/")[-1]
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                "orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser"
            ),
            params={
                "searchText": folder_name,
                "skip": skip,
                "take": take,
            },
        )

    def _list_spec(
        self,
        filter: Optional[str],
        orderby: Optional[str],
        skip: int,
        top: int,
    ) -> RequestSpec:
        """Build OData request for listing folders."""
        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if filter:
            params["$filter"] = filter
        if orderby:
            params["$orderby"] = orderby

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Folders"),
            params=params,
        )

    def _retrieve_folder_spec(
        self,
        key: Optional[str],
        display_name: Optional[str],
    ) -> RequestSpec:
        """Build request for retrieving folder by key or display name."""
        filters = []
        if key:
            pass
        if display_name:
            escaped_name = display_name.replace("'", "''")
            filters.append(f"DisplayName eq '{escaped_name}'")

        filter_str = " or ".join(filters) if filters else None

        params: Dict[str, Any] = {"$top": 1 if filters else 100}
        if filter_str:
            params["$filter"] = filter_str

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Folders"),
            params=params,
        )

    def _retrieve_by_path_spec(
        self,
        folder_path: str,
    ) -> RequestSpec:
        """Build request for retrieving folder by fully qualified path."""
        escaped_path = folder_path.replace("'", "''")
        params: Dict[str, Any] = {
            "$filter": f"FullyQualifiedName eq '{escaped_path}'",
            "$top": 1,
        }

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Folders"),
            params=params,
        )
