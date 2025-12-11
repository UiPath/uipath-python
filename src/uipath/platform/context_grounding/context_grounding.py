"""Context Grounding response payload models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BatchTransformOutputColumn(BaseModel):
    """Model representing a batch transform output column."""

    name: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"^[\w\s\.,!?-]+$",
    )
    description: str = Field(..., min_length=1, max_length=20000)

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )


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


class Citation(BaseModel):
    """Model representing a deep RAG citation."""

    ordinal: int
    page_number: int = Field(alias="pageNumber")
    source: str
    reference: str

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )


class DeepRagContent(BaseModel):
    """Model representing a deep RAG task content."""

    text: str
    citations: list[Citation]

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


class BatchTransformStatus(str, Enum):
    """Enum representing possible batch transform status values."""

    IN_PROGRESS = "InProgress"
    SUCCESSFUL = "Successful"
    QUEUED = "Queued"
    FAILED = "Failed"


class BatchTransformCreationResponse(BaseModel):
    """Model representing a batch transform task creation response."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )
    id: str
    last_batch_rag_status: DeepRagStatus = Field(alias="lastBatchRagStatus")
    error_message: str | None = Field(alias="errorMessage", default=None)


class BatchTransformResponse(BaseModel):
    """Model representing a batch transform task response."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )
    id: str
    name: str
    last_batch_rag_status: BatchTransformStatus = Field(alias="lastBatchRagStatus")
    prompt: str
    target_file_glob_pattern: str = Field(alias="targetFileGlobPattern")
    use_web_search_grounding: bool = Field(alias="useWebSearchGrounding")
    output_columns: list[BatchTransformOutputColumn] = Field(alias="outputColumns")
    created_date: str = Field(alias="createdDate")


class BatchTransformReadUriResponse(BaseModel):
    """Model representing a batch transform result file download URI response."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )
    uri: str


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
