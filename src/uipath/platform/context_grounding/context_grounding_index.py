"""Models for Context Grounding Index in the UiPath platform."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

class ContextGroundingField(BaseModel):
    """Model representing a field in a Context Grounding Index."""

    id: str | None = Field(default=None, alias="id")
    name: str | None = Field(default=None, alias="name")
    description: str | None = Field(default=None, alias="description")
    type: str | None = Field(default=None, alias="type")
    is_filterable: bool | None = Field(default=None, alias="isFilterable")
    searchable_type: str | None = Field(default=None, alias="searchableType")
    is_user_defined: bool | None = Field(default=None, alias="isUserDefined")

class ContextGroundingDataSource(BaseModel):
    """Model representing a data source in a Context Grounding Index."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    id: str | None = Field(default=None, alias="id")
    folder: str | None = Field(default=None, alias="folder")
    bucketName: str | None = Field(default=None, alias="bucketName")

class ContextGroundingIndex(BaseModel):
    """Model representing a Context Grounding Index in the UiPath platform."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("last_ingested", "last_queried", when_used="json")
    def serialize_datetime(self, value):
        """Serialize datetime fields to ISO 8601 format for JSON output."""
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    id: str | None = Field(default=None, alias="id")
    name: str | None = Field(default=None, alias="name")
    description: str | None = Field(default=None, alias="description")
    memory_usage: int | None = Field(default=None, alias="memoryUsage")
    disk_usage: int | None = Field(default=None, alias="diskUsage")
    data_source: ContextGroundingDataSource | None = Field(
        default=None, alias="dataSource"
    )
    pre_processing: Any = Field(default=None, alias="preProcessing")
    fields: list[ContextGroundingField] | None = Field(default=None, alias="fields")
    last_ingestion_status: str | None = Field(
        default=None, alias="lastIngestionStatus"
    )
    last_ingested: datetime | None = Field(default=None, alias="lastIngested")
    last_queried: datetime | None = Field(default=None, alias="lastQueried")
    folder_key: str | None = Field(default=None, alias="folderKey")

    def in_progress_ingestion(self):
        """Check if the last ingestion is in progress."""
        return (
            self.last_ingestion_status == "Queued"
            or self.last_ingestion_status == "In Progress"
        )
