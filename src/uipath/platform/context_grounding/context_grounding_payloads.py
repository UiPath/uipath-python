"""Payload models for context grounding index creation and configuration."""

import re
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from uipath._utils.constants import (
    CONFLUENCE_DATA_SOURCE_REQUEST,
    DROPBOX_DATA_SOURCE_REQUEST,
    GOOGLE_DRIVE_DATA_SOURCE_REQUEST,
    ONEDRIVE_DATA_SOURCE_REQUEST,
    ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE_REQUEST,
)


class BaseDataSource(BaseModel):
    """Base model for data source configurations."""

    folder: str = Field(alias="folder", description="Folder path")
    file_name_glob: str = Field(
        alias="fileNameGlob", description="File name glob pattern"
    )
    directory_path: str = Field(alias="directoryPath", description="Directory path")


class BucketDataSource(BaseDataSource):
    """Data source configuration for storage buckets."""

    odata_type: str = Field(
        alias="@odata.type",
        default=ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE_REQUEST,
    )
    bucket_name: str = Field(alias="bucketName", description="Storage bucket name")


class GoogleDriveDataSource(BaseDataSource):
    """Data source configuration for Google Drive."""

    odata_type: str = Field(
        alias="@odata.type",
        default=GOOGLE_DRIVE_DATA_SOURCE_REQUEST,
    )
    connection_id: str = Field(alias="connectionId", description="Connection ID")
    connection_name: str = Field(alias="connectionName", description="Connection name")
    leaf_folder_id: str = Field(alias="leafFolderId", description="Leaf folder ID")


class DropboxDataSource(BaseDataSource):
    """Data source configuration for Dropbox."""

    odata_type: str = Field(
        alias="@odata.type",
        default=DROPBOX_DATA_SOURCE_REQUEST,
    )
    connection_id: str = Field(alias="connectionId", description="Connection ID")
    connection_name: str = Field(alias="connectionName", description="Connection name")


class OneDriveDataSource(BaseDataSource):
    """Data source configuration for OneDrive."""

    odata_type: str = Field(
        alias="@odata.type",
        default=ONEDRIVE_DATA_SOURCE_REQUEST,
    )
    connection_id: str = Field(alias="connectionId", description="Connection ID")
    connection_name: str = Field(alias="connectionName", description="Connection name")
    leaf_folder_id: str = Field(alias="leafFolderId", description="Leaf folder ID")


class ConfluenceDataSource(BaseDataSource):
    """Data source configuration for Confluence."""

    odata_type: str = Field(
        alias="@odata.type",
        default=CONFLUENCE_DATA_SOURCE_REQUEST,
    )
    connection_id: str = Field(alias="connectionId", description="Connection ID")
    connection_name: str = Field(alias="connectionName", description="Connection name")
    space_id: str = Field(alias="spaceId", description="Space ID")


class AttachmentsDataSource(BaseModel):
    """Data source configuration for Attachments."""

    attachments: list[str] = Field(description="List of attachment ids")


class Indexer(BaseModel):
    """Configuration for periodic indexing of data sources."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    cron_expression: str = Field(description="Cron expression for scheduling")
    time_zone_id: str = Field(default="UTC", description="Time zone ID")

    @model_validator(mode="before")
    @classmethod
    def validate_cron(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cron expression format."""
        cron_expr = values.get("cron_expression") or values.get("cronExpression")
        if not cron_expr:
            return values

        # Supports @aliases, @every syntax and standard cron expressions with 5-7 fields
        cron_pattern = r"^(@(annually|yearly|monthly|weekly|daily|hourly|reboot))|(@every (\d+(ns|us|µs|ms|s|m|h))+)|((((\d+,)+\d+|(\d+(\/|-)\d+)|\d+|\*) ?){5,7})$"

        if not re.match(cron_pattern, cron_expr.strip(), re.IGNORECASE):
            raise ValueError(f"Invalid cron expression format: '{cron_expr}'")

        return values


class CreateIndexPayload(BaseModel):
    """Payload for creating a context grounding index.

    Note: data_source is Dict[str, Any] because it may contain additional
    fields like 'indexer' that are added dynamically based on configuration.
    The data source is still validated through the _build_data_source method
    which uses typed models internally.
    """

    name: str = Field(description="Index name")
    description: str = Field(default="", description="Index description")
    data_source: Dict[str, Any] = Field(
        alias="dataSource", description="Data source configuration"
    )
    extraction_strategy: Optional[str] = Field(
        default=None,
        alias="extractionStrategy",
        description="Extraction method: 'NativeV1' or 'LLMV4'. Defaults to NativeV1",
    )
    embeddings_enabled: Optional[bool] = Field(
        default=None,
        alias="embeddingsEnabled",
        description="Whether to generate embeddings. Defaults to true",
    )
    is_encrypted: Optional[bool] = Field(
        default=None,
        alias="isEncrypted",
        description="Whether to encrypt the index. Defaults to false",
    )

    model_config = ConfigDict(populate_by_name=True)


class CreateEphemeralIndexPayload(BaseModel):
    """Payload for creating an ephemeral context grounding index.

    Note: data_source is Dict[str, Any] because it may contain additional
    fields like 'indexer' that are added dynamically based on configuration.
    The data source is still validated through the _build_data_source method
    which uses typed models internally.
    """

    usage: str = Field(description="Index usage")
    data_source: Dict[str, Any] = Field(
        alias="dataSource", description="Data source configuration"
    )

    model_config = ConfigDict(populate_by_name=True)


# user-facing source configuration models
class BaseSourceConfig(BaseModel):
    """Base configuration for all source types."""

    folder_path: str = Field(description="Folder path in orchestrator")
    directory_path: str = Field(description="Directory path")
    file_type: Optional[str] = Field(
        default=None, description="File type filter (e.g., 'pdf', 'txt')"
    )
    indexer: Optional[Indexer] = Field(
        default=None, description="Optional indexer configuration for periodic updates"
    )


class ConnectionSourceConfig(BaseSourceConfig):
    """Base configuration for sources that use connections."""

    connection_id: str = Field(description="Connection ID")
    connection_name: str = Field(description="Connection name")


class BucketSourceConfig(BaseSourceConfig):
    """Data source configuration for storage buckets."""

    type: Literal["bucket"] = Field(
        default="bucket", description="Source type identifier"
    )
    bucket_name: str = Field(description="Storage bucket name")
    directory_path: str = Field(default="/", description="Directory path in bucket")


class GoogleDriveSourceConfig(ConnectionSourceConfig):
    """Data source configuration for Google Drive."""

    type: Literal["google_drive"] = Field(
        default="google_drive", description="Source type identifier"
    )
    leaf_folder_id: str = Field(description="Leaf folder ID in Google Drive")


class DropboxSourceConfig(ConnectionSourceConfig):
    """Data source configuration for Dropbox."""

    type: Literal["dropbox"] = Field(
        default="dropbox", description="Source type identifier"
    )


class OneDriveSourceConfig(ConnectionSourceConfig):
    """Data source configuration for OneDrive."""

    type: Literal["onedrive"] = Field(
        default="onedrive", description="Source type identifier"
    )
    leaf_folder_id: str = Field(description="Leaf folder ID in OneDrive")


class ConfluenceSourceConfig(ConnectionSourceConfig):
    """Data source configuration for Confluence."""

    type: Literal["confluence"] = Field(
        default="confluence", description="Source type identifier"
    )
    space_id: str = Field(description="Confluence space ID")


SourceConfig = Union[
    BucketSourceConfig,
    GoogleDriveSourceConfig,
    DropboxSourceConfig,
    OneDriveSourceConfig,
    ConfluenceSourceConfig,
]
