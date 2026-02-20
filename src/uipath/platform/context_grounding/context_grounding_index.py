"""Models for Context Grounding Index in the UiPath platform."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ContextGroundingDataSource(BaseModel):
    """Model representing a data source in a Context Grounding Index."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    id: Optional[str] = Field(default=None, alias="id")
    folder: Optional[str] = Field(default=None, alias="folder")
    bucketName: Optional[str] = Field(default=None, alias="bucketName")


class ContextGroundingIndexHealth(BaseModel):
    """Model representing health metrics for a Context Grounding Index."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    schema_id: Optional[str] = Field(default=None, alias="schemaId")
    ingestion_reliability_score: Optional[float] = Field(
        default=None, alias="ingestionReliabilityScore"
    )
    utilization_score: Optional[float] = Field(default=None, alias="utilizationScore")
    overall_health_score: Optional[float] = Field(
        default=None, alias="overallHealthScore"
    )
    health_status: Optional[str] = Field(default=None, alias="healthStatus")


class ContextGroundingIndex(BaseModel):
    """Model representing a Context Grounding Index in the UiPath platform."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("last_ingested", "last_queried")
    def serialize_datetime(self, value):
        """Serialize datetime fields to ISO 8601 format."""
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    id: Optional[str] = Field(default=None, alias="id")
    name: Optional[str] = Field(default=None, alias="name")
    description: Optional[str] = Field(default=None, alias="description")
    is_encrypted: Optional[bool] = Field(default=None, alias="isEncrypted")
    folder_fully_qualified_name: Optional[str] = Field(
        default=None, alias="folderFullyQualifiedName"
    )
    memory_usage: Optional[int] = Field(default=None, alias="memoryUsage")
    disk_usage: Optional[int] = Field(default=None, alias="diskUsage")
    extraction_strategy: Optional[str] = Field(
        default=None, alias="extractionStrategy"
    )
    embeddings_enabled: Optional[bool] = Field(
        default=None, alias="embeddingsEnabled"
    )
    data_source: Optional[ContextGroundingDataSource] = Field(
        default=None, alias="dataSource"
    )
    last_ingestion_status: Optional[str] = Field(
        default=None, alias="lastIngestionStatus"
    )
    last_ingestion_failure_reason: Optional[str] = Field(
        default=None, alias="lastIngestionFailureReason"
    )
    last_ingested: Optional[datetime] = Field(default=None, alias="lastIngested")
    last_queried: Optional[datetime] = Field(default=None, alias="lastQueried")
    folder_key: Optional[str] = Field(default=None, alias="folderKey")
    index_health: Optional[ContextGroundingIndexHealth] = Field(
        default=None, alias="indexHealth"
    )

    def in_progress_ingestion(self):
        """Check if the last ingestion is in progress."""
        return (
            self.last_ingestion_status == "Queued"
            or self.last_ingestion_status == "InProgress"
        )
