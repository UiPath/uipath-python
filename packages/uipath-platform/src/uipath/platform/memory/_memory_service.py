"""Episodic Memory service backed by ECS v2."""

from typing import Optional

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from .memory import (
    EpisodicMemoryCreateRequest,
    EpisodicMemoryIndex,
    EpisodicMemoryIngestRequest,
    EpisodicMemoryIngestResponse,
    EpisodicMemoryListResponse,
    EpisodicMemoryPatchRequest,
    EpisodicMemorySearchRequest,
    EpisodicMemorySearchResult,
    EpisodicMemoryStatus,
)

_BASE = "/ecs_/v2/episodicmemories"


class MemoryService(FolderContext, BaseService):
    """Service for Agent Episodic Memory backed by the ECS service.

    Agent Memory allows agents to persist context across jobs using dynamic
    few-shot retrieval. Memory indexes are folder-scoped and use
    Index.Create/Read/Update/Delete permissions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    # ── Index operations ───────────────────────────────────────────────

    @traced(name="memory_create", run_type="uipath")
    def create(
        self,
        name: str,
        description: Optional[str] = None,
        is_encrypted: Optional[bool] = None,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryIndex:
        """Create a new episodic memory index.

        Args:
            name: The name of the memory index (max 128 chars).
            description: Optional description (max 1024 chars).
            is_encrypted: Whether the index should be encrypted.
            folder_key: The folder key for the operation.

        Returns:
            EpisodicMemoryIndex: The created memory index.
        """
        spec = self._create_spec(name, description, is_encrypted, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        ).json()
        return EpisodicMemoryIndex.model_validate(response)

    @traced(name="memory_create", run_type="uipath")
    async def create_async(
        self,
        name: str,
        description: Optional[str] = None,
        is_encrypted: Optional[bool] = None,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryIndex:
        """Asynchronously create a new episodic memory index."""
        spec = self._create_spec(name, description, is_encrypted, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
        ).json()
        return EpisodicMemoryIndex.model_validate(response)

    @traced(name="memory_list", run_type="uipath")
    def list(
        self,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryListResponse:
        """List episodic memory indexes with optional OData query parameters.

        Args:
            filter: OData $filter expression.
            orderby: OData $orderby expression.
            top: Maximum number of results.
            skip: Number of results to skip.
            folder_key: The folder key for the operation.

        Returns:
            EpisodicMemoryListResponse: The list of memory indexes.
        """
        spec = self._list_spec(filter, orderby, top, skip, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()
        return EpisodicMemoryListResponse.model_validate(response)

    @traced(name="memory_list", run_type="uipath")
    async def list_async(
        self,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryListResponse:
        """Asynchronously list episodic memory indexes."""
        spec = self._list_spec(filter, orderby, top, skip, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()
        return EpisodicMemoryListResponse.model_validate(response)

    @traced(name="memory_get", run_type="uipath")
    def get(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryIndex:
        """Get a single episodic memory index by ID.

        Args:
            key: The GUID of the memory index.
            folder_key: The folder key for the operation.

        Returns:
            EpisodicMemoryIndex: The memory index.
        """
        spec = self._get_spec(key, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        ).json()
        return EpisodicMemoryIndex.model_validate(response)

    @traced(name="memory_get", run_type="uipath")
    async def get_async(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryIndex:
        """Asynchronously get a single episodic memory index by ID."""
        spec = self._get_spec(key, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                headers=spec.headers,
            )
        ).json()
        return EpisodicMemoryIndex.model_validate(response)

    @traced(name="memory_delete_index", run_type="uipath")
    def delete_index(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete an episodic memory index.

        Args:
            key: The GUID of the memory index.
            folder_key: The folder key for the operation.
        """
        spec = self._delete_index_spec(key, folder_key)
        self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="memory_delete_index", run_type="uipath")
    async def delete_index_async(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Asynchronously delete an episodic memory index."""
        spec = self._delete_index_spec(key, folder_key)
        await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    # ── Memory item operations ─────────────────────────────────────────

    @traced(name="memory_ingest", run_type="uipath")
    def ingest(
        self,
        key: str,
        request: EpisodicMemoryIngestRequest,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryIngestResponse:
        """Ingest a memory item into the specified index.

        Args:
            key: The GUID of the memory index.
            request: The ingest request payload.
            folder_key: The folder key for the operation.

        Returns:
            EpisodicMemoryIngestResponse: The ID of the created memory.
        """
        spec = self._ingest_spec(key, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        ).json()
        return EpisodicMemoryIngestResponse.model_validate(response)

    @traced(name="memory_ingest", run_type="uipath")
    async def ingest_async(
        self,
        key: str,
        request: EpisodicMemoryIngestRequest,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemoryIngestResponse:
        """Asynchronously ingest a memory item into the specified index."""
        spec = self._ingest_spec(key, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=request.model_dump(by_alias=True, exclude_none=True),
                headers=spec.headers,
            )
        ).json()
        return EpisodicMemoryIngestResponse.model_validate(response)

    @traced(name="memory_search", run_type="uipath")
    def search(
        self,
        key: str,
        request: EpisodicMemorySearchRequest,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemorySearchResult:
        """Perform semantic/hybrid search on episodic memory.

        Args:
            key: The GUID of the memory index.
            request: The search request payload.
            folder_key: The folder key for the operation.

        Returns:
            EpisodicMemorySearchResult: The search results with scores.
        """
        spec = self._search_spec(key, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        ).json()
        return EpisodicMemorySearchResult.model_validate(response)

    @traced(name="memory_search", run_type="uipath")
    async def search_async(
        self,
        key: str,
        request: EpisodicMemorySearchRequest,
        folder_key: Optional[str] = None,
    ) -> EpisodicMemorySearchResult:
        """Asynchronously perform semantic/hybrid search on episodic memory."""
        spec = self._search_spec(key, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=request.model_dump(by_alias=True, exclude_none=True),
                headers=spec.headers,
            )
        ).json()
        return EpisodicMemorySearchResult.model_validate(response)

    @traced(name="memory_patch", run_type="uipath")
    def patch_memory(
        self,
        key: str,
        memory_id: str,
        status: EpisodicMemoryStatus,
        folder_key: Optional[str] = None,
    ) -> None:
        """Update a memory item's status (active/inactive).

        Args:
            key: The GUID of the memory index.
            memory_id: The GUID of the memory item.
            status: The new status.
            folder_key: The folder key for the operation.
        """
        spec = self._patch_memory_spec(key, memory_id, folder_key)
        body = EpisodicMemoryPatchRequest(status=status)
        self.request(
            spec.method,
            spec.endpoint,
            json=body.model_dump(by_alias=True),
            headers=spec.headers,
        )

    @traced(name="memory_patch", run_type="uipath")
    async def patch_memory_async(
        self,
        key: str,
        memory_id: str,
        status: EpisodicMemoryStatus,
        folder_key: Optional[str] = None,
    ) -> None:
        """Asynchronously update a memory item's status."""
        spec = self._patch_memory_spec(key, memory_id, folder_key)
        body = EpisodicMemoryPatchRequest(status=status)
        await self.request_async(
            spec.method,
            spec.endpoint,
            json=body.model_dump(by_alias=True),
            headers=spec.headers,
        )

    @traced(name="memory_delete", run_type="uipath")
    def delete_memory(
        self,
        key: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete a memory item by ID.

        Args:
            key: The GUID of the memory index.
            memory_id: The GUID of the memory item.
            folder_key: The folder key for the operation.
        """
        spec = self._delete_memory_spec(key, memory_id, folder_key)
        self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="memory_delete", run_type="uipath")
    async def delete_memory_async(
        self,
        key: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Asynchronously delete a memory item by ID."""
        spec = self._delete_memory_spec(key, memory_id, folder_key)
        await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    # ── Private spec builders ─────────────────────────────────────────

    def _resolve_folder(self, folder_key: Optional[str]) -> Optional[str]:
        """Resolve the folder key, falling back to the context default."""
        return folder_key or self._folder_key

    def _create_spec(
        self,
        name: str,
        description: Optional[str],
        is_encrypted: Optional[bool],
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        body = EpisodicMemoryCreateRequest(
            name=name,
            description=description,
            is_encrypted=is_encrypted,
        )
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_BASE}/create"),
            json=body.model_dump(by_alias=True, exclude_none=True),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _list_spec(
        self,
        filter: Optional[str],
        orderby: Optional[str],
        top: Optional[int],
        skip: Optional[int],
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        params: dict = {}
        if filter is not None:
            params["$filter"] = filter
        if orderby is not None:
            params["$orderby"] = orderby
        if top is not None:
            params["$top"] = top
        if skip is not None:
            params["$skip"] = skip
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(_BASE),
            params=params,
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _get_spec(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_BASE}/{key}"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _delete_index_spec(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"{_BASE}/{key}"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _ingest_spec(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_BASE}/{key}/ingest"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _search_spec(
        self,
        key: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_BASE}/{key}/search"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _patch_memory_spec(
        self,
        key: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="PATCH",
            endpoint=Endpoint(f"{_BASE}({key})/memory({memory_id})"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _delete_memory_spec(
        self,
        key: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"{_BASE}({key})/memory({memory_id})"),
            headers={
                **header_folder(folder_key, None),
            },
        )
