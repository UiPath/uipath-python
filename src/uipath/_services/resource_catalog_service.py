from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._folder_context import FolderContext
from uipath._services import FolderService
from uipath._services._base_service import BaseService
from uipath._utils import Endpoint, RequestSpec, header_folder
from uipath.models.resource_catalog import Resource, ResourceType
from uipath.tracing import traced


class ResourceCatalogService(FolderContext, BaseService):
    """Service for searching and discovering UiPath resources across folders.

    The Resource Catalog Service provides a centralized way to search and retrieve
    UiPath resources (assets, queues, processes, storage buckets, etc.) across
    tenant and folder scopes. It enables programmatic discovery of resources with
    flexible filtering by resource type, name, and folder location.

    See Also:
        https://docs.uipath.com/orchestrator/standalone/2024.10/user-guide/about-resource-catalog-service

    !!! info "Version Availability"
        This service is available starting from **uipath** version **2.1.168**.
    """

    _DEFAULT_PAGE_SIZE = 20

    def __init__(
        self,
        config: Config,
        execution_context: ExecutionContext,
        folder_service: FolderService,
    ) -> None:
        self.folder_service = folder_service
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="resource_catalog_search", run_type="uipath")
    def search(
        self,
        *,
        name: Optional[str] = None,
        resource_types: Optional[List[ResourceType]] = None,
        resource_sub_types: Optional[List[str]] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> Iterator[Resource]:
        """Search for tenant scoped resources and folder scoped resources (accessible to the user).

        This method automatically handles pagination and yields resources one by one.

        Args:
            name: Optional name filter for resources
            resource_types: Optional list of resource types to filter by
            resource_sub_types: Optional list of resource subtypes to filter by
            page_size: Number of resources to fetch per API call (default: 20, max: 100)

        Yields:
            Resource: Each resource matching the search criteria

        Examples:
            >>> # Search for all resources with "invoice" in the name
            >>> for resource in uipath.resource_catalog.search(name="invoice"):
            ...     print(f"{resource.name}: {resource.resource_type}")

            >>> # Search for specific resource types
            >>> for resource in uipath.resource_catalog.search(
            ...     resource_types=[ResourceType.ASSET]
            ... ):
            ...     print(resource.name)
        """
        skip = 0
        take = min(page_size, 100)

        while True:
            spec = self._search_spec(
                name=name,
                resource_types=resource_types,
                resource_sub_types=resource_sub_types,
                skip=skip,
                take=take,
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
                yield Resource.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="resource_catalog_search", run_type="uipath")
    async def search_async(
        self,
        *,
        name: Optional[str] = None,
        resource_types: Optional[List[ResourceType]] = None,
        resource_sub_types: Optional[List[str]] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[Resource]:
        """Asynchronously search for tenant scoped resources and folder scoped resources (accessible to the user).

        This method automatically handles pagination and yields resources one by one.

        Args:
            name: Optional name filter for resources
            resource_types: Optional list of resource types to filter by
            resource_sub_types: Optional list of resource subtypes to filter by
            page_size: Number of resources to fetch per API call (default: 20, max: 100)

        Yields:
            Resource: Each resource matching the search criteria

        Examples:
            >>> # Search for all resources with "invoice" in the name
            >>> async for resource in uipath.resource_catalog.search_async(name="invoice"):
            ...     print(f"{resource.name}: {resource.resource_type}")

            >>> # Search for specific resource types
            >>> async for resource in uipath.resource_catalog.search_async(
            ...     resource_types=[ResourceType.ASSET]
            ... ):
            ...     print(resource.name)
        """
        skip = 0
        take = min(page_size, 100)

        while True:
            spec = self._search_spec(
                name=name,
                resource_types=resource_types,
                resource_sub_types=resource_sub_types,
                skip=skip,
                take=take,
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
                yield Resource.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="resource_catalog_list", run_type="uipath")
    def list(
        self,
        *,
        resource_types: Optional[List[ResourceType]] = None,
        resource_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> Iterator[Resource]:
        """Get tenant scoped resources and folder scoped resources (accessible to the user).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields resources one by one.

        Args:
            resource_types: Optional list of resource types to filter by
            resource_sub_types: Optional list of resource subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of resources to fetch per API call (default: 20, max: 100)

        Yields:
            Resource: Each resource matching the criteria

        Examples:
            >>> # Get all resources
            >>> for resource in uipath.resource_catalog.list():
            ...     print(f"{resource.name}: {resource.resource_type}")

            >>> # Get specific resource types
            >>> assets = list(uipath.resource_catalog.list(
            ...     resource_types=[ResourceType.ASSET],
            ... ))

            >>> # Get resources within a specific folder
            >>> for resource in uipath.resource_catalog.list(
            ...     folder_path="/Shared/Finance",
            ...     resource_types=[ResourceType.ASSET],
            ...     resource_sub_types=["number"]
            ... ):
            ...     print(resource.name)
        """
        skip = 0
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = self.folder_service.retrieve_folder_key(folder_path)

        while True:
            spec = self._list_spec(
                resource_types=resource_types,
                resource_sub_types=resource_sub_types,
                folder_key=resolved_folder_key,
                skip=skip,
                take=take,
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
                yield Resource.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="resource_catalog_list", run_type="uipath")
    async def list_async(
        self,
        *,
        resource_types: Optional[List[ResourceType]] = None,
        resource_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[Resource]:
        """Asynchronously get tenant scoped resources and folder scoped resources (accessible to the user).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields resources one by one.

        Args:
            resource_types: Optional list of resource types to filter by
            resource_sub_types: Optional list of resource subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of resources to fetch per API call (default: 20, max: 100)

        Yields:
            Resource: Each resource matching the criteria

        Examples:
            >>> # Get all resources
            >>> async for resource in uipath.resource_catalog.list_async():
            ...     print(f"{resource.name}: {resource.resource_type}")

            >>> # Get specific resource types
            >>> assets = []
            >>> async for resource in uipath.resource_catalog.list_async(
            ...     resource_types=[ResourceType.ASSET],
            ... ):
            ...     assets.append(resource)

            >>> # Get resources within a specific folder
            >>> async for resource in uipath.resource_catalog.list_async(
            ...     folder_path="/Shared/Finance",
            ...     resource_types=[ResourceType.ASSET],
            ...     resource_sub_types=["number"]
            ... ):
            ...     print(resource.name)
        """
        skip = 0
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = await self.folder_service.retrieve_folder_key_async(
            folder_path
        )
        while True:
            spec = self._list_spec(
                resource_types=resource_types,
                resource_sub_types=resource_sub_types,
                folder_key=resolved_folder_key,
                skip=skip,
                take=take,
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
                yield Resource.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="list_by_type", run_type="uipath")
    def list_by_type(
        self,
        *,
        resource_type: ResourceType,
        name: Optional[str] = None,
        resource_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> Iterator[Resource]:
        """Get resources of a specific type (tenant scoped or folder scoped).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields resources one by one.

        Args:
            resource_type: The specific resource type to filter by
            name: Optional name filter for resources
            resource_sub_types: Optional list of resource subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of resources to fetch per API call (default: 20, max: 100)

        Yields:
            Resource: Each resource matching the criteria

        Examples:
            >>> # Get all assets
            >>> for resource in uipath.resource_catalog.list_by_type(resource_type=ResourceType.ASSET):
            ...     print(f"{resource.name}: {resource.resource_sub_type}")

            >>> # Get assets with a specific name pattern
            >>> assets = list(uipath.resource_catalog.list_by_type(
            ...     resource_type=ResourceType.ASSET,
            ...     name="config"
            ... ))

            >>> # Get assets within a specific folder with subtype filter
            >>> for resource in uipath.resource_catalog.list_by_type(
            ...     resource_type=ResourceType.ASSET,
            ...     folder_path="/Shared/Finance",
            ...     resource_sub_types=["number"]
            ... ):
            ...     print(resource.name)
        """
        skip = 0
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = self.folder_service.retrieve_folder_key(folder_path)

        while True:
            spec = self._list_by_type_spec(
                resource_type=resource_type,
                name=name,
                resource_sub_types=resource_sub_types,
                folder_key=resolved_folder_key,
                skip=skip,
                take=take,
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
                yield Resource.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="list_by_type_async", run_type="uipath")
    async def list_by_type_async(
        self,
        *,
        resource_type: ResourceType,
        name: Optional[str] = None,
        resource_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[Resource]:
        """Asynchronously get resources of a specific type (tenant scoped or folder scoped).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields resources one by one.

        Args:
            resource_type: The specific resource type to filter by
            name: Optional name filter for resources
            resource_sub_types: Optional list of resource subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of resources to fetch per API call (default: 20, max: 100)

        Yields:
            Resource: Each resource matching the criteria

        Examples:
            >>> # Get all assets asynchronously
            >>> async for resource in uipath.resource_catalog.list_by_type_async(resource_type=ResourceType.ASSET):
            ...     print(f"{resource.name}: {resource.resource_sub_type}")

            >>> # Get assets with a specific name pattern
            >>> assets = []
            >>> async for resource in uipath.resource_catalog.list_by_type_async(
            ...     resource_type=ResourceType.ASSET,
            ...     name="config"
            ... ):
            ...     assets.append(resource)

            >>> # Get assets within a specific folder with subtype filter
            >>> async for resource in uipath.resource_catalog.list_by_type_async(
            ...     resource_type=ResourceType.ASSET,
            ...     folder_path="/Shared/Finance",
            ...     resource_sub_types=["number"]
            ... ):
            ...     print(resource.name)
        """
        skip = 0
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = await self.folder_service.retrieve_folder_key_async(
            folder_path
        )

        while True:
            spec = self._list_by_type_spec(
                resource_type=resource_type,
                name=name,
                resource_sub_types=resource_sub_types,
                folder_key=resolved_folder_key,
                skip=skip,
                take=take,
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
                yield Resource.model_validate(item)

            if len(items) < take:
                break

            skip += take

    def _search_spec(
        self,
        name: Optional[str],
        resource_types: Optional[List[ResourceType]],
        resource_sub_types: Optional[List[str]],
        skip: int,
        take: int,
    ) -> RequestSpec:
        """Build the request specification for searching resources.

        Args:
            name: Optional name filter
            resource_types: Optional resource types filter
            resource_sub_types: Optional resource subtypes filter
            skip: Number of resources to skip (for pagination)
            take: Number of resources to take

        Returns:
            RequestSpec: The request specification for the API call
        """
        params: Dict[str, Any] = {
            "skip": skip,
            "take": take,
        }

        if name:
            params["name"] = name

        if resource_types:
            params["entityTypes"] = [x.value for x in resource_types]

        if resource_sub_types:
            params["entitySubType"] = resource_sub_types

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("resourcecatalog_/Entities/Search"),
            params=params,
        )

    def _list_spec(
        self,
        resource_types: Optional[List[ResourceType]],
        resource_sub_types: Optional[List[str]],
        folder_key: Optional[str],
        skip: int,
        take: int,
    ) -> RequestSpec:
        """Build the request specification for getting resources.

        Args:
            resource_types: Optional resource types filter
            resource_sub_types: Optional resource subtypes filter
            folder_key: Optional folder key to scope the results
            skip: Number of resources to skip (for pagination)
            take: Number of resources to take

        Returns:
            RequestSpec: The request specification for the API call
        """
        params: Dict[str, Any] = {
            "skip": skip,
            "take": take,
        }

        if resource_types:
            params["entityTypes"] = [x.value for x in resource_types]

        if resource_sub_types:
            params["entitySubType"] = resource_sub_types

        headers = {
            **header_folder(folder_key, None),
        }

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("resourcecatalog_/Entities"),
            params=params,
            headers=headers,
        )

    def _list_by_type_spec(
        self,
        resource_type: ResourceType,
        name: Optional[str],
        resource_sub_types: Optional[List[str]],
        folder_key: Optional[str],
        skip: int,
        take: int,
    ) -> RequestSpec:
        """Build the request specification for getting resources.

        Args:
            resource_type: Resource type
            resource_sub_types: Optional resource subtypes filter
            folder_key: Optional folder key to scope the results
            skip: Number of resources to skip (for pagination)
            take: Number of resources to take

        Returns:
            RequestSpec: The request specification for the API call
        """
        params: Dict[str, Any] = {
            "skip": skip,
            "take": take,
        }

        if name:
            params["name"] = name

        if resource_sub_types:
            params["entitySubType"] = resource_sub_types

        headers = {
            **header_folder(folder_key, None),
        }

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"resourcecatalog_/Entities/{resource_type.value}"),
            params=params,
            headers=headers,
        )
