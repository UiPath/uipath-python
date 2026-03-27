"""Pydantic models for the Episodic Memory API (ECS v2)."""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── Enums ──────────────────────────────────────────────────────────────


class SearchMode(str, Enum):
    """Search mode for episodic memory queries."""

    hybrid = "hybrid"
    semantic = "semantic"


class EpisodicMemoryStatus(str, Enum):
    """Status of an individual memory record."""

    active = "active"
    inactive = "inactive"


# ── Field models ───────────────────────────────────────────────────────


class EpisodicMemoryField(BaseModel):
    """A field with a key path and value, used in ingest and search requests."""

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
    """A field in a search request, with optional per-field settings."""

    model_config = ConfigDict(populate_by_name=True)

    key_path: List[str] = Field(..., alias="keyPath", min_length=1)
    value: str = Field(..., alias="value", min_length=1)
    settings: Optional[FieldSettings] = Field(None, alias="settings")


# ── Request models ─────────────────────────────────────────────────────


class EpisodicMemoryCreateRequest(BaseModel):
    """Request payload for creating an episodic memory index."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., alias="name", max_length=128, min_length=1)
    description: Optional[str] = Field(None, alias="description", max_length=1024)
    is_encrypted: Optional[bool] = Field(None, alias="isEncrypted")


class EpisodicMemoryIngestRequest(BaseModel):
    """Request payload for ingesting a memory item."""

    model_config = ConfigDict(populate_by_name=True)

    fields: List[EpisodicMemoryField] = Field(
        ..., alias="fields", min_length=1, max_length=20
    )


class SearchSettings(BaseModel):
    """Top-level search settings."""

    model_config = ConfigDict(populate_by_name=True)

    threshold: float = Field(default=0.0, alias="threshold", ge=0.0, le=1.0)
    result_count: int = Field(default=1, alias="resultCount", ge=1, le=10)
    search_mode: SearchMode = Field(..., alias="searchMode")


class EpisodicMemorySearchRequest(BaseModel):
    """Request payload for searching episodic memory."""

    model_config = ConfigDict(populate_by_name=True)

    fields: List[SearchField] = Field(..., alias="fields", min_length=1, max_length=20)
    settings: SearchSettings = Field(..., alias="settings")


class EpisodicMemoryPatchRequest(BaseModel):
    """Request payload for updating a memory item's status."""

    model_config = ConfigDict(populate_by_name=True)

    status: EpisodicMemoryStatus = Field(..., alias="status")


# ── Response models ────────────────────────────────────────────────────


class EpisodicMemoryIndex(BaseModel):
    """An episodic memory index (folder-scoped)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="id")
    name: str = Field(..., alias="name")
    description: Optional[str] = Field(None, alias="description")
    last_queried: Optional[str] = Field(None, alias="lastQueried")
    memories_count: int = Field(default=0, alias="memoriesCount")
    folder_key: str = Field(..., alias="folderKey")
    created_by_user_id: Optional[str] = Field(None, alias="createdByUserId")
    is_encrypted: bool = Field(default=False, alias="isEncrypted")


class EpisodicMemoryIngestResponse(BaseModel):
    """Response from an ingest operation, containing the new memory ID."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="id")


class MemoryMatchField(BaseModel):
    """A field within a search result, with scoring details."""

    model_config = ConfigDict(populate_by_name=True)

    key_path: List[str] = Field(..., alias="keyPath")
    value: str = Field(..., alias="value")
    weight: float = Field(..., alias="weight")
    score: float = Field(..., alias="score")
    semantic_score: float = Field(..., alias="semanticScore")
    weighted_score: float = Field(..., alias="weightedScore")


class MemoryMatch(BaseModel):
    """A single matched memory from a search operation."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="id")
    score: float = Field(..., alias="score")
    semantic_score: float = Field(..., alias="semanticScore")
    weighted_score: float = Field(..., alias="weightedScore")
    fields: List[MemoryMatchField] = Field(..., alias="fields")


class EpisodicMemorySearchResult(BaseModel):
    """Response from a search operation."""

    model_config = ConfigDict(populate_by_name=True)

    results: List[MemoryMatch] = Field(default_factory=list, alias="results")
    metadata: Dict[str, str] = Field(default_factory=dict, alias="metadata")


class EpisodicMemoryListResponse(BaseModel):
    """OData response from listing episodic memory indexes."""

    model_config = ConfigDict(populate_by_name=True)

    value: List[EpisodicMemoryIndex] = Field(default_factory=list, alias="value")
