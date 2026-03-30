"""Pydantic models for the Episodic Memory API.

Index management goes through ECS v2.  Search goes through LLMOps,
which enriches traces/feedback before forwarding to ECS.
Escalation memory operations also go through LLMOps.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── Enums ──────────────────────────────────────────────────────────────


class SearchMode(str, Enum):
    """Search mode for episodic memory queries."""

    Hybrid = "Hybrid"
    Semantic = "Semantic"


class EpisodicMemoryStatus(str, Enum):
    """Status of an individual memory record (ECS)."""

    active = "active"
    inactive = "inactive"


# ── Shared field models (used by both ECS and LLMOps) ─────────────────


class EpisodicMemoryField(BaseModel):
    """A field with a key path and value, used in ECS ingest requests."""

    model_config = ConfigDict(populate_by_name=True)

    key_path: List[str] = Field(..., alias="keyPath", min_length=1)
    value: str = Field(..., alias="value", min_length=1)


class FieldSettings(BaseModel):
    """Per-field search settings (optional overrides)."""

    model_config = ConfigDict(populate_by_name=True)

    weight: float = Field(default=1.0, alias="weight", ge=0.0, le=1.0)
    threshold: Optional[float] = Field(None, alias="threshold", ge=0.0, le=1.0)
    search_mode: Optional[SearchMode] = Field(None, alias="searchMode")


class SearchField(BaseModel):
    """A field in a search request, with per-field settings."""

    model_config = ConfigDict(populate_by_name=True)

    key_path: List[str] = Field(..., alias="keyPath", min_length=1)
    value: str = Field(..., alias="value", min_length=1)
    settings: FieldSettings = Field(default_factory=FieldSettings, alias="settings")


class SearchSettings(BaseModel):
    """Top-level search settings."""

    model_config = ConfigDict(populate_by_name=True)

    threshold: float = Field(default=0.0, alias="threshold", ge=0.0, le=1.0)
    result_count: int = Field(default=1, alias="resultCount", ge=1, le=10)
    search_mode: SearchMode = Field(..., alias="searchMode")


class MemoryMatchField(BaseModel):
    """A field within a search result, with scoring details."""

    model_config = ConfigDict(populate_by_name=True)

    key_path: List[str] = Field(..., alias="keyPath")
    value: str = Field(..., alias="value")
    weight: float = Field(..., alias="weight")
    score: float = Field(..., alias="score")
    weighted_score: float = Field(..., alias="weightedScore")


# ── ECS request models (index CRUD) ───────────────────────────────────


class EpisodicMemoryCreateRequest(BaseModel):
    """Request payload for creating an episodic memory index (ECS)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., alias="name", max_length=128, min_length=1)
    description: Optional[str] = Field(None, alias="description", max_length=1024)
    is_encrypted: Optional[bool] = Field(None, alias="isEncrypted")


# ── ECS response models ───────────────────────────────────────────────


class EpisodicMemoryIndex(BaseModel):
    """An episodic memory index (folder-scoped, from ECS)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="id")
    name: str = Field(..., alias="name")
    description: Optional[str] = Field(None, alias="description")
    last_queried: Optional[str] = Field(None, alias="lastQueried")
    memories_count: int = Field(default=0, alias="memoriesCount")
    folder_key: str = Field(..., alias="folderKey")
    created_by_user_id: Optional[str] = Field(None, alias="createdByUserId")
    is_encrypted: bool = Field(default=False, alias="isEncrypted")


class EpisodicMemoryListResponse(BaseModel):
    """OData response from listing episodic memory indexes (ECS)."""

    model_config = ConfigDict(populate_by_name=True)

    value: List[EpisodicMemoryIndex] = Field(default_factory=list, alias="value")


# ── LLMOps search models ──────────────────────────────────────────────


class MemorySearchRequest(BaseModel):
    """Request payload for searching memory via LLMOps.

    Includes definitionSystemPrompt so LLMOps can generate the
    systemPromptInjection for the agent loop.
    """

    model_config = ConfigDict(populate_by_name=True)

    fields: List[SearchField] = Field(..., alias="fields", min_length=1, max_length=20)
    settings: SearchSettings = Field(..., alias="settings")
    definition_system_prompt: Optional[str] = Field(
        None, alias="definitionSystemPrompt"
    )


class MemoryMatch(BaseModel):
    """A single matched memory from a search operation (LLMOps)."""

    model_config = ConfigDict(populate_by_name=True)

    memory_item_id: str = Field(..., alias="memoryItemId")
    score: float = Field(..., alias="score")
    semantic_score: float = Field(..., alias="semanticScore")
    weighted_score: float = Field(..., alias="weightedScore")
    fields: List[MemoryMatchField] = Field(..., alias="fields")
    span: Optional[Any] = Field(None, alias="span")
    feedback: Optional[Any] = Field(None, alias="feedback")


class MemorySearchResponse(BaseModel):
    """Response from LLMOps search, including system prompt injection."""

    model_config = ConfigDict(populate_by_name=True)

    results: List[MemoryMatch] = Field(default_factory=list, alias="results")
    metadata: Dict[str, str] = Field(default_factory=dict, alias="metadata")
    system_prompt_injection: str = Field("", alias="systemPromptInjection")


# ── LLMOps escalation memory models ──────────────────────────────────


class EscalationMemoryIngestRequest(BaseModel):
    """Request payload for ingesting an escalation outcome into memory.

    Used by the escalation tool to persist resolved outcomes so
    future runs can recall them without re-escalating.
    """

    model_config = ConfigDict(populate_by_name=True)

    span_id: str = Field(..., alias="spanId")
    trace_id: str = Field(..., alias="traceId")
    answer: str = Field(..., alias="answer")
    attributes: str = Field(..., alias="attributes")
    user_id: Optional[str] = Field(None, alias="userId")


class CachedRecall(BaseModel):
    """A cached escalation answer retrieved from memory."""

    model_config = ConfigDict(populate_by_name=True)

    output: Optional[Any] = Field(None, alias="output")
    outcome: Optional[str] = Field(None, alias="outcome")


class EscalationMemoryMatch(BaseModel):
    """A single match from an escalation memory search."""

    model_config = ConfigDict(populate_by_name=True)

    answer: Optional[CachedRecall] = Field(None, alias="answer")


class EscalationMemorySearchResponse(BaseModel):
    """Response from LLMOps escalation memory search."""

    model_config = ConfigDict(populate_by_name=True)

    results: Optional[List[EscalationMemoryMatch]] = Field(None, alias="results")
