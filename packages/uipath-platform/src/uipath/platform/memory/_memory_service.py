"""Memory service for Agent Episodic Memory backed by ECS."""

from typing import Optional

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from .memory import (
    MemoryIngestRequest,
    MemoryItem,
    MemoryListResponse,
    MemoryQueryRequest,
    MemoryQueryResponse,
    MemoryResource,
)


class MemoryService(FolderContext, BaseService):
    """Service for Agent Episodic Memory backed by the ECS service.

    Agent Memory allows agents to persist context across jobs using dynamic
    few-shot retrieval. Memory resources are folder-scoped (like CG indexes)
    and use Index.Create/Read/Update/Delete permissions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    # ── Public methods ────────────────────────────────────────────────

    @traced(name="memory_create", run_type="uipath")
    def create(
        self,
        name: str,
        description: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> MemoryResource:
        """Create a new memory resource.

        Args:
            name: The name of the memory resource.
            description: Optional description.
            folder_key: The folder key for the operation.

        Returns:
            MemoryResource: The created memory resource.
        """
        spec = self._create_spec(name, description, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        ).json()
        return MemoryResource.model_validate(response)

    @traced(name="memory_create", run_type="uipath")
    async def create_async(
        self,
        name: str,
        description: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> MemoryResource:
        """Asynchronously create a new memory resource.

        Args:
            name: The name of the memory resource.
            description: Optional description.
            folder_key: The folder key for the operation.

        Returns:
            MemoryResource: The created memory resource.
        """
        spec = self._create_spec(name, description, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
        ).json()
        return MemoryResource.model_validate(response)

    @traced(name="memory_ingest", run_type="uipath")
    def ingest(
        self,
        name: str,
        request: MemoryIngestRequest,
        folder_key: Optional[str] = None,
    ) -> None:
        """Ingest a memory item into the specified memory resource.

        Args:
            name: The name of the memory resource.
            request: The ingest request payload.
            folder_key: The folder key for the operation.
        """
        spec = self._ingest_spec(name, folder_key)
        self.request(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        )

    @traced(name="memory_ingest", run_type="uipath")
    async def ingest_async(
        self,
        name: str,
        request: MemoryIngestRequest,
        folder_key: Optional[str] = None,
    ) -> None:
        """Asynchronously ingest a memory item into the specified memory resource.

        Args:
            name: The name of the memory resource.
            request: The ingest request payload.
            folder_key: The folder key for the operation.
        """
        spec = self._ingest_spec(name, folder_key)
        await self.request_async(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        )

    @traced(name="memory_query", run_type="uipath")
    def query(
        self,
        name: str,
        request: MemoryQueryRequest,
        folder_key: Optional[str] = None,
    ) -> MemoryQueryResponse:
        """Perform semantic search on memory.

        Args:
            name: The name of the memory resource.
            request: The query request payload.
            folder_key: The folder key for the operation.

        Returns:
            MemoryQueryResponse: The query results.
        """
        spec = self._query_spec(name, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        ).json()
        return MemoryQueryResponse.model_validate(response)

    @traced(name="memory_query", run_type="uipath")
    async def query_async(
        self,
        name: str,
        request: MemoryQueryRequest,
        folder_key: Optional[str] = None,
    ) -> MemoryQueryResponse:
        """Asynchronously perform semantic search on memory.

        Args:
            name: The name of the memory resource.
            request: The query request payload.
            folder_key: The folder key for the operation.

        Returns:
            MemoryQueryResponse: The query results.
        """
        spec = self._query_spec(name, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=request.model_dump(by_alias=True, exclude_none=True),
                headers=spec.headers,
            )
        ).json()
        return MemoryQueryResponse.model_validate(response)

    @traced(name="memory_retrieve", run_type="uipath")
    def retrieve(
        self,
        name: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> MemoryItem:
        """Retrieve a single memory item by ID.

        Args:
            name: The name of the memory resource.
            memory_id: The ID of the memory item to retrieve.
            folder_key: The folder key for the operation.

        Returns:
            MemoryItem: The retrieved memory item.
        """
        spec = self._retrieve_spec(name, memory_id, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        ).json()
        return MemoryItem.model_validate(response)

    @traced(name="memory_retrieve", run_type="uipath")
    async def retrieve_async(
        self,
        name: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> MemoryItem:
        """Asynchronously retrieve a single memory item by ID.

        Args:
            name: The name of the memory resource.
            memory_id: The ID of the memory item to retrieve.
            folder_key: The folder key for the operation.

        Returns:
            MemoryItem: The retrieved memory item.
        """
        spec = self._retrieve_spec(name, memory_id, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                headers=spec.headers,
            )
        ).json()
        return MemoryItem.model_validate(response)

    @traced(name="memory_delete", run_type="uipath")
    def delete(
        self,
        name: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete a memory item by ID.

        Args:
            name: The name of the memory resource.
            memory_id: The ID of the memory item to delete.
            folder_key: The folder key for the operation.
        """
        spec = self._delete_spec(name, memory_id, folder_key)
        self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="memory_delete", run_type="uipath")
    async def delete_async(
        self,
        name: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Asynchronously delete a memory item by ID.

        Args:
            name: The name of the memory resource.
            memory_id: The ID of the memory item to delete.
            folder_key: The folder key for the operation.
        """
        spec = self._delete_spec(name, memory_id, folder_key)
        await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="memory_list", run_type="uipath")
    def list(
        self,
        name: str,
        folder_key: Optional[str] = None,
    ) -> MemoryListResponse:
        """List all memory items in a memory resource.

        Args:
            name: The name of the memory resource.
            folder_key: The folder key for the operation.

        Returns:
            MemoryListResponse: The list of memory items.
        """
        spec = self._list_spec(name, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        ).json()
        return MemoryListResponse.model_validate(response)

    @traced(name="memory_list", run_type="uipath")
    async def list_async(
        self,
        name: str,
        folder_key: Optional[str] = None,
    ) -> MemoryListResponse:
        """Asynchronously list all memory items in a memory resource.

        Args:
            name: The name of the memory resource.
            folder_key: The folder key for the operation.

        Returns:
            MemoryListResponse: The list of memory items.
        """
        spec = self._list_spec(name, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                headers=spec.headers,
            )
        ).json()
        return MemoryListResponse.model_validate(response)

    # ── Private spec builders ─────────────────────────────────────────

    def _resolve_folder(self, folder_key: Optional[str]) -> Optional[str]:
        """Resolve the folder key, falling back to the context default."""
        return folder_key or self._folder_key

    def _create_spec(
        self,
        name: str,
        description: Optional[str],
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/ecs_/memory/create"),
            json={
                "name": name,
                "description": description,
            },
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _ingest_spec(
        self,
        name: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/memory/{name}/ingest"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _query_spec(
        self,
        name: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/memory/{name}/query"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _retrieve_spec(
        self,
        name: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/memory/{name}/{memory_id}"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _delete_spec(
        self,
        name: str,
        memory_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"/ecs_/memory/{name}/{memory_id}"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _list_spec(
        self,
        name: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/memory/{name}/list"),
            headers={
                **header_folder(folder_key, None),
            },
        )
