"""Context Grounding response payload models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CitationMode(str, Enum):
    """Enum representing possible citation modes."""

    SKIP = "Skip"
    INLINE = "Inline"


class DeepRagStatus(str, Enum):
    """Enum representing possible deep RAG tasks status."""

    QUEUED = "Queued"
    IN_PROGRESS = "InProgress"
    SUCCESSFUL = "Successful"
    FAILED = "Failed"


class DeepRagContent(BaseModel):
    """Model representing a deep RAG task content."""

    text: str
    citations: list[str]

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )


class DeepRagResponse(BaseModel):
    """Model representing a deep RAG task response."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    name: str
    created_date: str = Field(alias="createdDate")
    last_deep_rag_status: DeepRagStatus = Field(alias="lastDeepRagStatus")
    content: DeepRagContent | None = Field(alias="content")


class DeepRagCreationResponse(BaseModel):
    """Model representing a deep RAG task creation response."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    id: str
    last_deep_rag_status: DeepRagStatus = Field(alias="lastDeepRagStatus")
    created_date: str = Field(alias="createdDate")


class ContextGroundingMetadata(BaseModel):
    """Model representing metadata for a Context Grounding query response."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    operation_id: str = Field(alias="operation_id")
    strategy: str = Field(alias="strategy")


class ContextGroundingQueryResponse(BaseModel):
    """Model representing a Context Grounding query response item."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    source: str = Field(alias="source")
    page_number: str = Field(alias="page_number")
    content: str = Field(alias="content")
    metadata: ContextGroundingMetadata = Field(alias="metadata")
    source_document_id: Optional[str] = Field(default=None, alias="source_document_id")
    caption: Optional[str] = Field(default=None, alias="caption")
    score: Optional[float] = Field(default=None, alias="score")
    reference: Optional[str] = Field(default=None, alias="reference")
