from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._folder_context import FolderContext
from uipath._services import FolderService
from uipath._services._base_service import BaseService
from uipath._utils import Endpoint, RequestSpec, header_folder
from uipath.models.resource_catalog import EntityType, ResourceEntity
from uipath.tracing import traced


class ResourceCatalogService(FolderContext, BaseService):
    """Service for searching and discovering UiPath resources across folders.

    The Resource Catalog Service provides a centralized way to search and retrieve
    UiPath resources (assets, queues, processes, storage buckets, etc.) across
    tenant and folder scopes. It enables programmatic discovery of resources with
    flexible filtering by entity type, name, and folder location.

    See Also:
        https://docs.uipath.com/orchestrator/standalone/2024.10/user-guide/about-resource-catalog-service
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

    @traced(name="resource_catalog_search_entities", run_type="uipath")
    def search(
        self,
        *,
        name: Optional[str] = None,
        entity_types: Optional[List[EntityType]] = None,
        entity_sub_types: Optional[List[str]] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> Iterator[ResourceEntity]:
        """Search for tenant scoped entities and folder scoped entities (accessible to the user).

        This method automatically handles pagination and yields entities one by one.

        Args:
            name: Optional name filter for entities
            entity_types: Optional list of entity types to filter by
            entity_sub_types: Optional list of entity subtypes to filter by
            page_size: Number of entities to fetch per API call (default: 20, max: 100)

        Yields:
            ResourceEntity: Each entity matching the search criteria

        Examples:
            >>> # Search for all entities with "invoice" in the name
            >>> for entity in uipath.resource_catalog.search(name="invoice"):
            ...     print(f"{entity.name}: {entity.entity_type}")

            >>> # Search for specific entity types
            >>> for entity in uipath.resource_catalog.search(
            ...     entity_types=[EntityType.ASSET]
            ... ):
            ...     print(entity.name)
        """
        skip = 0
        # limit page sizes to 100
        take = min(page_size, 100)

        while True:
            spec = self._search_spec(
                name=name,
                entity_types=entity_types,
                entity_sub_types=entity_sub_types,
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
                yield ResourceEntity.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="resource_catalog_search_entities", run_type="uipath")
    async def search_async(
        self,
        *,
        name: Optional[str] = None,
        entity_types: Optional[List[EntityType]] = None,
        entity_sub_types: Optional[List[str]] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[ResourceEntity]:
        """Asynchronously search for tenant scoped entities and folder scoped entities (accessible to the user).

        This method automatically handles pagination and yields entities one by one.

        Args:
            name: Optional name filter for entities
            entity_types: Optional list of entity types to filter by
            entity_sub_types: Optional list of entity subtypes to filter by
            page_size: Number of entities to fetch per API call (default: 20, max: 100)

        Yields:
            ResourceEntity: Each entity matching the search criteria

        Examples:
            >>> # Search for all entities with "invoice" in the name
            >>> async for entity in uipath.resource_catalog.search_entities_across_folders_async(name="invoice"):
            ...     print(f"{entity.name}: {entity.entity_type}")

            >>> # Search for specific entity types
            >>> async for entity in uipath.resource_catalog.search_entities_across_folders_async(
            ...     entity_types=[EntityType.ASSET]
            ... ):
            ...     print(entity.name)
        """
        skip = 0
        # limit page sizes to 100
        take = min(page_size, 100)

        while True:
            spec = self._search_spec(
                name=name,
                entity_types=entity_types,
                entity_sub_types=entity_sub_types,
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
                yield ResourceEntity.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="resource_catalog_list_entities", run_type="uipath")
    def list(
        self,
        *,
        entity_types: Optional[List[EntityType]] = None,
        entity_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> Iterator[ResourceEntity]:
        """Get tenant scoped entities and folder scoped entities (accessible to the user).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields entities one by one.

        Args:
            entity_types: Optional list of entity types to filter by
            entity_sub_types: Optional list of entity subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of entities to fetch per API call (default: 20, max: 100)

        Yields:
            ResourceEntity: Each entity matching the criteria

        Examples:
            >>> # Get all entities
            >>> for entity in uipath.resource_catalog.list():
            ...     print(f"{entity.name}: {entity.entity_type}")

            >>> # Get specific entity types
            >>> assets = list(uipath.resource_catalog.list(
            ...     entity_types=[EntityType.ASSET],
            ... ))

            >>> # Get entities within a specific folder
            >>> for entity in uipath.resource_catalog.list(
            ...     folder_path="/Shared/Finance",
            ...     entity_types=[EntityType.ASSET],
            ...     entity_sub_types=["number"]
            ... ):
            ...     print(entity.name)
        """
        skip = 0
        # limit page sizes to 100
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = self.folder_service.retrieve_folder_key(folder_path)

        while True:
            spec = self._list_spec(
                entity_types=entity_types,
                entity_sub_types=entity_sub_types,
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
                yield ResourceEntity.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="resource_catalog_list_entities", run_type="uipath")
    async def list_async(
        self,
        *,
        entity_types: Optional[List[EntityType]] = None,
        entity_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[ResourceEntity]:
        """Asynchronously get tenant scoped entities and folder scoped entities (accessible to the user).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields entities one by one.

        Args:
            entity_types: Optional list of entity types to filter by
            entity_sub_types: Optional list of entity subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of entities to fetch per API call (default: 20, max: 100)

        Yields:
            ResourceEntity: Each entity matching the criteria

        Examples:
            >>> # Get all entities
            >>> async for entity in uipath.resource_catalog.list_async():
            ...     print(f"{entity.name}: {entity.entity_type}")

            >>> # Get specific entity types
            >>> assets = []
            >>> async for entity in uipath.resource_catalog.list_async(
            ...     entity_types=[EntityType.ASSET],
            ... ):
            ...     assets.append(entity)

            >>> # Get entities within a specific folder
            >>> async for entity in uipath.resource_catalog.list_async(
            ...     folder_path="/Shared/Finance",
            ...     entity_types=[EntityType.ASSET],
            ...     entity_sub_types=["number"]
            ... ):
            ...     print(entity.name)
        """
        skip = 0
        # limit page sizes to 100
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = await self.folder_service.retrieve_folder_key_async(
            folder_path
        )
        while True:
            spec = self._list_spec(
                entity_types=entity_types,
                entity_sub_types=entity_sub_types,
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
                yield ResourceEntity.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="list_by_type", run_type="uipath")
    def list_by_type(
        self,
        *,
        entity_type: EntityType,
        name: Optional[str] = None,
        entity_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> Iterator[ResourceEntity]:
        """Get entities of a specific type (tenant scoped or folder scoped).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields entities one by one.

        Args:
            entity_type: The specific entity type to filter by
            name: Optional name filter for entities
            entity_sub_types: Optional list of entity subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of entities to fetch per API call (default: 20, max: 100)

        Yields:
            ResourceEntity: Each entity matching the criteria

        Examples:
            >>> # Get all assets
            >>> for entity in uipath.resource_catalog.list_by_type(entity_type=EntityType.ASSET):
            ...     print(f"{entity.name}: {entity.entity_sub_type}")

            >>> # Get assets with a specific name pattern
            >>> assets = list(uipath.resource_catalog.list_by_type(
            ...     entity_type=EntityType.ASSET,
            ...     name="config"
            ... ))

            >>> # Get assets within a specific folder with subtype filter
            >>> for entity in uipath.resource_catalog.list_by_type(
            ...     entity_type=EntityType.ASSET,
            ...     folder_path="/Shared/Finance",
            ...     entity_sub_types=["number"]
            ... ):
            ...     print(entity.name)
        """
        skip = 0
        # limit page sizes to 100
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = self.folder_service.retrieve_folder_key(folder_path)

        while True:
            spec = self._list_by_type_spec(
                entity_type=entity_type,
                name=name,
                entity_sub_types=entity_sub_types,
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
                yield ResourceEntity.model_validate(item)

            if len(items) < take:
                break

            skip += take

    @traced(name="list_by_type_async", run_type="uipath")
    async def list_by_type_async(
        self,
        *,
        entity_type: EntityType,
        name: Optional[str] = None,
        entity_sub_types: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[ResourceEntity]:
        """Asynchronously get entities of a specific type (tenant scoped or folder scoped).

        If no folder identifier is provided (path or key) only tenant resources will be retrieved.
        This method automatically handles pagination and yields entities one by one.

        Args:
            entity_type: The specific entity type to filter by
            name: Optional name filter for entities
            entity_sub_types: Optional list of entity subtypes to filter by
            folder_path: Optional folder path to scope the results
            folder_key: Optional folder key to scope the results
            page_size: Number of entities to fetch per API call (default: 20, max: 100)

        Yields:
            ResourceEntity: Each entity matching the criteria

        Examples:
            >>> # Get all assets asynchronously
            >>> async for entity in uipath.resource_catalog.list_by_type_async(entity_type=EntityType.ASSET):
            ...     print(f"{entity.name}: {entity.entity_sub_type}")

            >>> # Get assets with a specific name pattern
            >>> assets = []
            >>> async for entity in uipath.resource_catalog.list_by_type_async(
            ...     entity_type=EntityType.ASSET,
            ...     name="config"
            ... ):
            ...     assets.append(entity)

            >>> # Get assets within a specific folder with subtype filter
            >>> async for entity in uipath.resource_catalog.list_by_type_async(
            ...     entity_type=EntityType.ASSET,
            ...     folder_path="/Shared/Finance",
            ...     entity_sub_types=["number"]
            ... ):
            ...     print(entity.name)
        """
        skip = 0
        # limit page sizes to 100
        take = min(page_size, 100)

        if take <= 0:
            raise ValueError(f"page_size must be greater than 0. Got {page_size}")

        resolved_folder_key = await self.folder_service.retrieve_folder_key_async(
            folder_path
        )

        while True:
            spec = self._list_by_type_spec(
                entity_type=entity_type,
                name=name,
                entity_sub_types=entity_sub_types,
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
                yield ResourceEntity.model_validate(item)

            if len(items) < take:
                break

            skip += take

    def _search_spec(
        self,
        name: Optional[str],
        entity_types: Optional[List[EntityType]],
        entity_sub_types: Optional[List[str]],
        skip: int,
        take: int,
    ) -> RequestSpec:
        """Build the request specification for searching entities.

        Args:
            name: Optional name filter
            entity_types: Optional entity types filter
            entity_sub_types: Optional entity subtypes filter
            skip: Number of entities to skip (for pagination)
            take: Number of entities to take

        Returns:
            RequestSpec: The request specification for the API call
        """
        params: Dict[str, Any] = {
            "skip": skip,
            "take": take,
        }

        if name:
            params["name"] = name

        if entity_types:
            params["entityTypes"] = [x.value for x in entity_types]

        if entity_sub_types:
            params["entitySubType"] = entity_sub_types

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("resourcecatalog_/Entities/Search"),
            params=params,
        )

    def _list_spec(
        self,
        entity_types: Optional[List[EntityType]],
        entity_sub_types: Optional[List[str]],
        folder_key: Optional[str],
        skip: int,
        take: int,
    ) -> RequestSpec:
        """Build the request specification for getting entities.

        Args:
            entity_types: Optional entity types filter
            entity_sub_types: Optional entity subtypes filter
            folder_key: Optional folder key to scope the results
            skip: Number of entities to skip (for pagination)
            take: Number of entities to take

        Returns:
            RequestSpec: The request specification for the API call
        """
        params: Dict[str, Any] = {
            "skip": skip,
            "take": take,
        }

        if entity_types:
            params["entityTypes"] = [x.value for x in entity_types]

        if entity_sub_types:
            params["entitySubType"] = entity_sub_types

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
        entity_type: EntityType,
        name: Optional[str],
        entity_sub_types: Optional[List[str]],
        folder_key: Optional[str],
        skip: int,
        take: int,
    ) -> RequestSpec:
        """Build the request specification for getting entities.

        Args:
            entity_type: Entity type
            entity_sub_types: Optional entity subtypes filter
            folder_key: Optional folder key to scope the results
            skip: Number of entities to skip (for pagination)
            take: Number of entities to take

        Returns:
            RequestSpec: The request specification for the API call
        """
        params: Dict[str, Any] = {
            "skip": skip,
            "take": take,
        }

        if name:
            params["name"] = name

        if entity_sub_types:
            params["entitySubType"] = entity_sub_types

        headers = {
            **header_folder(folder_key, None),
        }

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"resourcecatalog_/Entities/{entity_type.value}"),
            params=params,
            headers=headers,
        )
