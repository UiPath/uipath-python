"""Pydantic models for the Memory API."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryField(BaseModel):
    """A field name/value pair used in memory inputs and outputs."""

    model_config = ConfigDict(populate_by_name=True)

    field_name: str = Field(..., alias="fieldName")
    field_value: str = Field(..., alias="fieldValue")


class MemoryItem(BaseModel):
    """A single memory item containing inputs, outputs, and trace context."""

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(None, alias="id")
    trace_id: Optional[str] = Field(None, alias="traceId")
    feedback_item_id: Optional[str] = Field(None, alias="feedbackItemId")
    inputs: List[MemoryField] = Field(default_factory=list, alias="inputs")
    outputs: List[MemoryField] = Field(default_factory=list, alias="outputs")
    abbreviated_trace: Optional[List[str]] = Field(None, alias="abbreviatedTrace")
    partition_key: Optional[str] = Field(None, alias="partitionKey")


class MemoryQueryRequest(BaseModel):
    """Request payload for semantic search on memory."""

    model_config = ConfigDict(populate_by_name=True)

    inputs: List[MemoryField] = Field(..., alias="inputs")
    outputs: Optional[List[MemoryField]] = Field(None, alias="outputs")
    abbreviated_trace: Optional[List[str]] = Field(None, alias="abbreviatedTrace")
    top_k: int = Field(default=5, alias="topK")
    threshold: Optional[float] = Field(None, alias="threshold")
    partition_key: Optional[str] = Field(None, alias="partitionKey")


class MemoryQueryResult(BaseModel):
    """A single result from a memory query."""

    model_config = ConfigDict(populate_by_name=True)

    memory_item: MemoryItem = Field(..., alias="memoryItem")
    score: float = Field(..., alias="score")


class MemoryQueryResponse(BaseModel):
    """Response from a memory query operation."""

    model_config = ConfigDict(populate_by_name=True)

    results: List[MemoryQueryResult] = Field(default_factory=list, alias="results")


class MemoryIngestRequest(BaseModel):
    """Request payload for ingesting a memory item."""

    model_config = ConfigDict(populate_by_name=True)

    trace_id: Optional[str] = Field(None, alias="traceId")
    feedback_item_id: Optional[str] = Field(None, alias="feedbackItemId")
    inputs: List[MemoryField] = Field(..., alias="inputs")
    outputs: List[MemoryField] = Field(default_factory=list, alias="outputs")
    abbreviated_trace: Optional[List[str]] = Field(None, alias="abbreviatedTrace")
    partition_key: Optional[str] = Field(None, alias="partitionKey")


class MemoryResource(BaseModel):
    """A memory resource (folder-scoped, similar to CG indexes)."""

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(None, alias="id")
    name: str = Field(..., alias="name")
    description: Optional[str] = Field(None, alias="description")


class MemoryListResponse(BaseModel):
    """Response from listing memory items."""

    model_config = ConfigDict(populate_by_name=True)

    value: List[MemoryItem] = Field(default_factory=list, alias="value")
