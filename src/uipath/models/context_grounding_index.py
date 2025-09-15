from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ContextGroundingField(BaseModel):
    id: Optional[str] = Field(default=None, alias="id")
    name: Optional[str] = Field(default=None, alias="name")
    description: Optional[str] = Field(default=None, alias="description")
    type: Optional[str] = Field(default=None, alias="type")
    is_filterable: Optional[bool] = Field(default=None, alias="isFilterable")
    searchable_type: Optional[str] = Field(default=None, alias="searchableType")
    is_user_defined: Optional[bool] = Field(default=None, alias="isUserDefined")


class ContextGroundingDataSource(BaseModel):
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


class ContextGroundingIndex(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("last_ingested", "last_queried", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    id: Optional[str] = Field(default=None, alias="id")
    name: Optional[str] = Field(default=None, alias="name")
    description: Optional[str] = Field(default=None, alias="description")
    memory_usage: Optional[int] = Field(default=None, alias="memoryUsage")
    disk_usage: Optional[int] = Field(default=None, alias="diskUsage")
    data_source: Optional[ContextGroundingDataSource] = Field(
        default=None, alias="dataSource"
    )
    pre_processing: Any = Field(default=None, alias="preProcessing")
    fields: Optional[List[ContextGroundingField]] = Field(default=None, alias="fields")
    last_ingestion_status: Optional[str] = Field(
        default=None, alias="lastIngestionStatus"
    )
    last_ingested: Optional[datetime] = Field(default=None, alias="lastIngested")
    last_queried: Optional[datetime] = Field(default=None, alias="lastQueried")
    folder_key: Optional[str] = Field(default=None, alias="folderKey")

    def in_progress_ingestion(self):
        return (
            self.last_ingestion_status == "Queued"
            or self.last_ingestion_status == "In Progress"
        )
