"""Episodic Memory service.

Index management (create/list/get/delete) goes through ECS v2.
Ingest and search go through LLMOps, which enriches traces/feedback
before forwarding to ECS.
"""

from typing import Any, Optional

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from .memory import (
    EpisodicMemoryCreateRequest,
    EpisodicMemoryIndex,
    EpisodicMemoryListResponse,
    FeedbackMemoryStatus,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryItemResponse,
    MemoryItemUpdateRequest,
    MemorySearchRequest,
    MemorySearchResponse,
)

_ECS_BASE = "/ecs_/v2/episodicmemories"
_LLMOPS_AGENT_BASE = "/llmopstenant_/api/Agent/memory"
_LLMOPS_MEMORY_BASE = "/llmopstenant_/api/Memory"


class MemoryService(FolderContext, BaseService):
    """Service for Agent Episodic Memory.

    Agent Memory allows agents to persist context across jobs using dynamic
    few-shot retrieval. Memory indexes are folder-scoped and managed via ECS.
    Ingestion and search are routed through LLMOps, which handles
    trace/feedback enrichment and system prompt injection.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    # ── Index operations (ECS) ─────────────────────────────────────────

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

    # ── Ingest (LLMOps) ───────────────────────────────────────────────

    @traced(name="memory_ingest", run_type="uipath")
    def ingest(
        self,
        memory_space_id: str,
        feedback_id: str,
        memory_space_name: Optional[str] = None,
        attributes: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> MemoryIngestResponse:
        """Ingest a memory item via LLMOps.

        LLMOps extracts fields from the trace/feedback and forwards
        the ingestion to ECS.

        Args:
            memory_space_id: The GUID of the memory space (ECS index).
            feedback_id: The GUID of the feedback to ingest from.
            memory_space_name: Optional name for the memory space.
            attributes: Optional JSON-encoded attributes.
            folder_key: The folder key for the operation.

        Returns:
            MemoryIngestResponse: The ID of the created memory item.
        """
        spec = self._ingest_spec(memory_space_id, memory_space_name, folder_key)
        body = MemoryIngestRequest(feedback_id=feedback_id, attributes=attributes)
        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
            json=body.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        ).json()
        return MemoryIngestResponse.model_validate(response)

    @traced(name="memory_ingest", run_type="uipath")
    async def ingest_async(
        self,
        memory_space_id: str,
        feedback_id: str,
        memory_space_name: Optional[str] = None,
        attributes: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> MemoryIngestResponse:
        """Asynchronously ingest a memory item via LLMOps."""
        spec = self._ingest_spec(memory_space_id, memory_space_name, folder_key)
        body = MemoryIngestRequest(feedback_id=feedback_id, attributes=attributes)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                params=spec.params,
                json=body.model_dump(by_alias=True, exclude_none=True),
                headers=spec.headers,
            )
        ).json()
        return MemoryIngestResponse.model_validate(response)

    # ── Search (LLMOps) ───────────────────────────────────────────────

    @traced(name="memory_search", run_type="uipath")
    def search(
        self,
        memory_space_id: str,
        request: MemorySearchRequest,
        folder_key: Optional[str] = None,
    ) -> MemorySearchResponse:
        """Search episodic memory via LLMOps.

        Returns search results with scores and a systemPromptInjection
        string ready for the agent loop.

        Args:
            memory_space_id: The GUID of the memory space (ECS index).
            request: The search request payload.
            folder_key: The folder key for the operation.

        Returns:
            MemorySearchResponse: Results, metadata, and system prompt injection.
        """
        spec = self._search_spec(memory_space_id, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        ).json()
        return MemorySearchResponse.model_validate(response)

    @traced(name="memory_search", run_type="uipath")
    async def search_async(
        self,
        memory_space_id: str,
        request: MemorySearchRequest,
        folder_key: Optional[str] = None,
    ) -> MemorySearchResponse:
        """Asynchronously search episodic memory via LLMOps."""
        spec = self._search_spec(memory_space_id, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=request.model_dump(by_alias=True, exclude_none=True),
                headers=spec.headers,
            )
        ).json()
        return MemorySearchResponse.model_validate(response)

    # ── Memory item operations (LLMOps) ───────────────────────────────

    @traced(name="memory_patch", run_type="uipath")
    def patch_memory(
        self,
        memory_space_id: str,
        memory_item_id: str,
        status: FeedbackMemoryStatus,
        folder_key: Optional[str] = None,
    ) -> MemoryItemResponse:
        """Update a memory item's status (Enabled/Disabled) via LLMOps.

        Args:
            memory_space_id: The GUID of the memory space.
            memory_item_id: The GUID of the memory item.
            status: The new status.
            folder_key: The folder key for the operation.

        Returns:
            MemoryItemResponse: The updated memory item.
        """
        spec = self._patch_memory_spec(memory_space_id, memory_item_id, folder_key)
        body = MemoryItemUpdateRequest(status=status)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=body.model_dump(by_alias=True),
            headers=spec.headers,
        ).json()
        return MemoryItemResponse.model_validate(response)

    @traced(name="memory_patch", run_type="uipath")
    async def patch_memory_async(
        self,
        memory_space_id: str,
        memory_item_id: str,
        status: FeedbackMemoryStatus,
        folder_key: Optional[str] = None,
    ) -> MemoryItemResponse:
        """Asynchronously update a memory item's status via LLMOps."""
        spec = self._patch_memory_spec(memory_space_id, memory_item_id, folder_key)
        body = MemoryItemUpdateRequest(status=status)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=body.model_dump(by_alias=True),
                headers=spec.headers,
            )
        ).json()
        return MemoryItemResponse.model_validate(response)

    @traced(name="memory_delete", run_type="uipath")
    def delete_memory(
        self,
        memory_space_id: str,
        memory_item_id: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete a memory item by ID via LLMOps.

        Args:
            memory_space_id: The GUID of the memory space.
            memory_item_id: The GUID of the memory item.
            folder_key: The folder key for the operation.
        """
        spec = self._delete_memory_spec(memory_space_id, memory_item_id, folder_key)
        self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="memory_delete", run_type="uipath")
    async def delete_memory_async(
        self,
        memory_space_id: str,
        memory_item_id: str,
        folder_key: Optional[str] = None,
    ) -> None:
        """Asynchronously delete a memory item by ID via LLMOps."""
        spec = self._delete_memory_spec(memory_space_id, memory_item_id, folder_key)
        await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    # ── Private spec builders ─────────────────────────────────────────

    def _resolve_folder(self, folder_key: Optional[str]) -> Optional[str]:
        return folder_key or self._folder_key

    # -- ECS specs --

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
            endpoint=Endpoint(f"{_ECS_BASE}/create"),
            json=body.model_dump(by_alias=True, exclude_none=True),
            headers={**header_folder(folder_key, None)},
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
        params: dict[str, Any] = {}
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
            endpoint=Endpoint(_ECS_BASE),
            params=params,
            headers={**header_folder(folder_key, None)},
        )

    def _get_spec(self, key: str, folder_key: Optional[str] = None) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_ECS_BASE}/{key}"),
            headers={**header_folder(folder_key, None)},
        )

    def _delete_index_spec(
        self, key: str, folder_key: Optional[str] = None
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"{_ECS_BASE}/{key}"),
            headers={**header_folder(folder_key, None)},
        )

    # -- LLMOps specs --

    def _ingest_spec(
        self,
        memory_space_id: str,
        memory_space_name: Optional[str],
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        params: dict[str, Any] = {}
        if memory_space_name is not None:
            params["memorySpaceName"] = memory_space_name
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_LLMOPS_AGENT_BASE}/{memory_space_id}/ingest"),
            params=params,
            headers={**header_folder(folder_key, None)},
        )

    def _search_spec(
        self,
        memory_space_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_LLMOPS_AGENT_BASE}/{memory_space_id}/search"),
            headers={**header_folder(folder_key, None)},
        )

    def _patch_memory_spec(
        self,
        memory_space_id: str,
        memory_item_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="PATCH",
            endpoint=Endpoint(
                f"{_LLMOPS_MEMORY_BASE}/{memory_space_id}/items/{memory_item_id}"
            ),
            headers={**header_folder(folder_key, None)},
        )

    def _delete_memory_spec(
        self,
        memory_space_id: str,
        memory_item_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(
                f"{_LLMOPS_MEMORY_BASE}/{memory_space_id}/items/{memory_item_id}"
            ),
            headers={**header_folder(folder_key, None)},
        )
