"""Episodic Memory service.

Index management (create/list) goes through ECS v2.
Search and escalation memory operations go through LLMOps, which
enriches traces/feedback before forwarding to ECS.
"""

from typing import Any, Optional

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from ..orchestrator._folder_service import FolderService
from .memory import (
    EpisodicMemoryCreateRequest,
    EpisodicMemoryIndex,
    EpisodicMemoryListResponse,
    EscalationMemoryIngestRequest,
    EscalationMemorySearchResponse,
    MemorySearchRequest,
    MemorySearchResponse,
)

_MEMORY_SPACES_BASE = "/ecs_/v2/episodicmemories"
_LLMOPS_AGENT_BASE = "/llmopstenant_/api/Agent/memory"


class MemoryService(FolderContext, BaseService):
    """Service for Agent Episodic Memory.

    Agent Memory allows agents to persist context across jobs using dynamic
    few-shot retrieval. Memory indexes are folder-scoped and managed via ECS.
    Search is routed through LLMOps, which handles trace/feedback enrichment
    and system prompt injection. Escalation memory enables agents to recall
    previously resolved escalation outcomes.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

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
        """Asynchronously create a new episodic memory index.

        Args:
            name: The name of the memory index (max 128 chars).
            description: Optional description (max 1024 chars).
            is_encrypted: Whether the index should be encrypted.
            folder_key: The folder key for the operation.

        Returns:
            EpisodicMemoryIndex: The created memory index.
        """
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
        """Asynchronously list episodic memory indexes.

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
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()
        return EpisodicMemoryListResponse.model_validate(response)

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
        """Asynchronously search episodic memory via LLMOps.

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
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=request.model_dump(by_alias=True, exclude_none=True),
                headers=spec.headers,
            )
        ).json()
        return MemorySearchResponse.model_validate(response)

    # ── Escalation memory (LLMOps) ────────────────────────────────────

    @traced(name="memory_escalation_search", run_type="uipath")
    def escalation_search(
        self,
        memory_space_id: str,
        request: MemorySearchRequest,
        folder_key: Optional[str] = None,
    ) -> EscalationMemorySearchResponse:
        """Search escalation memory for previously resolved outcomes.

        Allows agents to recall past escalation resolutions to avoid
        re-escalating for similar situations.

        Args:
            memory_space_id: The GUID of the memory space (ECS index).
            request: The search request payload (same as regular search).
            folder_key: The folder key for the operation.

        Returns:
            EscalationMemorySearchResponse: Matched escalation outcomes.
        """
        spec = self._escalation_search_spec(memory_space_id, folder_key)
        response = self.request(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        ).json()
        return EscalationMemorySearchResponse.model_validate(response)

    @traced(name="memory_escalation_search", run_type="uipath")
    async def escalation_search_async(
        self,
        memory_space_id: str,
        request: MemorySearchRequest,
        folder_key: Optional[str] = None,
    ) -> EscalationMemorySearchResponse:
        """Asynchronously search escalation memory for previously resolved outcomes.

        Allows agents to recall past escalation resolutions to avoid
        re-escalating for similar situations.

        Args:
            memory_space_id: The GUID of the memory space (ECS index).
            request: The search request payload (same as regular search).
            folder_key: The folder key for the operation.

        Returns:
            EscalationMemorySearchResponse: Matched escalation outcomes.
        """
        spec = self._escalation_search_spec(memory_space_id, folder_key)
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                json=request.model_dump(by_alias=True, exclude_none=True),
                headers=spec.headers,
            )
        ).json()
        return EscalationMemorySearchResponse.model_validate(response)

    @traced(name="memory_escalation_ingest", run_type="uipath")
    def escalation_ingest(
        self,
        memory_space_id: str,
        request: EscalationMemoryIngestRequest,
        folder_key: Optional[str] = None,
    ) -> None:
        """Ingest a resolved escalation outcome into memory.

        Persists the outcome so future agent runs can recall it
        without re-escalating.

        Args:
            memory_space_id: The GUID of the memory space (ECS index).
            request: The escalation ingest payload.
            folder_key: The folder key for the operation.
        """
        spec = self._escalation_ingest_spec(memory_space_id, folder_key)
        self.request(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        )

    @traced(name="memory_escalation_ingest", run_type="uipath")
    async def escalation_ingest_async(
        self,
        memory_space_id: str,
        request: EscalationMemoryIngestRequest,
        folder_key: Optional[str] = None,
    ) -> None:
        """Asynchronously ingest a resolved escalation outcome into memory.

        Persists the outcome so future agent runs can recall it
        without re-escalating.

        Args:
            memory_space_id: The GUID of the memory space (ECS index).
            request: The escalation ingest payload.
            folder_key: The folder key for the operation.
        """
        spec = self._escalation_ingest_spec(memory_space_id, folder_key)
        await self.request_async(
            spec.method,
            spec.endpoint,
            json=request.model_dump(by_alias=True, exclude_none=True),
            headers=spec.headers,
        )

    # ── Private spec builders ─────────────────────────────────────────

    def _resolve_folder(
        self,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve the folder key, supporting folder_path lookup for serverless.

        Priority:
        1. Explicit folder_key argument
        2. Explicit folder_path argument → resolve via FolderService
        3. UIPATH_FOLDER_KEY env var (via FolderContext._folder_key)
        4. UIPATH_FOLDER_PATH env var → resolve via FolderService
        """
        if folder_key is None and folder_path is not None:
            folder_key = self._folders_service.retrieve_key(folder_path=folder_path)

        if folder_key is None and folder_path is None:
            folder_key = self._folder_key or (
                self._folders_service.retrieve_key(folder_path=self._folder_path)
                if self._folder_path
                else None
            )

        return folder_key

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
            endpoint=Endpoint(f"{_MEMORY_SPACES_BASE}/create"),
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
            endpoint=Endpoint(_MEMORY_SPACES_BASE),
            params=params,
            headers={**header_folder(folder_key, None)},
        )

    # -- LLMOps specs --

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

    def _escalation_search_spec(
        self,
        memory_space_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{_LLMOPS_AGENT_BASE}/{memory_space_id}/escalation/search"
            ),
            headers={**header_folder(folder_key, None)},
        )

    def _escalation_ingest_spec(
        self,
        memory_space_id: str,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder(folder_key)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{_LLMOPS_AGENT_BASE}/{memory_space_id}/escalation/ingest"
            ),
            headers={**header_folder(folder_key, None)},
        )
