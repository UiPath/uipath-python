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


class EphemeralIndexUsage(str, Enum):
    """Enum representing possible ephemeral index usage types."""

    DEEP_RAG = "DeepRAG"
    BATCH_RAG = "BatchRAG"


class DeepRagStatus(str, Enum):
    """Enum representing possible deep RAG tasks status."""

    QUEUED = "Queued"
    IN_PROGRESS = "InProgress"
    SUCCESSFUL = "Successful"
    FAILED = "Failed"


class IndexStatus(str, Enum):
    """Enum representing possible index tasks status."""

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
    id: str
    name: str
    created_date: str = Field(alias="createdDate")
    last_deep_rag_status: DeepRagStatus = Field(alias="lastDeepRagStatus")
    content: DeepRagContent | None = Field(alias="content")
    failure_reason: str | None = Field(alias="failureReason", default=None)


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
    is_encrypted: bool = Field(alias="isEncrypted", default=False)


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


class ContextGroundingSearchResultItem(BaseModel):
    """Model representing a value item in a unified search (v1.2) semantic result."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    id: Optional[str | int] = Field(default=None, alias="id")
    content: str = Field(alias="content")
    source: str = Field(alias="source")
    page_number: int | str = Field(alias="page_number")
    score: Optional[float] = Field(default=None, alias="score")
    reference: Optional[str] = Field(default=None, alias="reference")
    source_document_id: Optional[str] = Field(default=None, alias="source_document_id")
    dataset_id: Optional[str] = Field(default=None, alias="dataset_id")
    datasource_id: Optional[str] = Field(default=None, alias="datasource_id")
    source_document_sha256: Optional[str] = Field(
        default=None, alias="source_document_sha256"
    )
    caption: Optional[str] = Field(default=None, alias="caption")


class SearchMode(str, Enum):
    """Enum representing possible unified search modes."""

    AUTO = "Auto"
    SEMANTIC = "Semantic"


class UnifiedSearchScope(BaseModel):
    """Model representing the scope for a unified search request."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    folder: Optional[str] = Field(default=None)
    extension: Optional[str] = Field(default=None)


class SemanticSearchOptions(BaseModel):
    """Model representing semantic search options for a unified search request."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    number_of_results: int = Field(default=3, alias="numberOfResults")
    threshold: float = Field(default=0.0)


class SemanticSearchResult(BaseModel):
    """Model representing a semantic search result from a unified search."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    values: list[ContextGroundingSearchResultItem] = Field(
        default_factory=list, alias="values"
    )
    metadata: Optional[ContextGroundingMetadata] = Field(default=None, alias="metadata")


class UnifiedQueryResult(BaseModel):
    """Model representing the result of a unified search query."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    semantic_results: Optional[SemanticSearchResult] = Field(
        default=None, alias="semanticResults"
    )
    explanation: Optional[str] = Field(default=None)
    index_id: Optional[str] = Field(default=None, alias="indexId")
