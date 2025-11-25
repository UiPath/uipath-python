"""Models for Orchestrator Buckets API responses."""

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

class BucketFile(BaseModel):
    """Represents a file within a bucket.

    Supports both ListFiles API (lowercase fields) and GetFiles API (PascalCase fields).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    full_path: str = Field(
        validation_alias=AliasChoices("fullPath", "FullPath"),
        description="Full path within bucket",
    )
    content_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("contentType", "ContentType"),
        description="MIME type",
    )
    size: int = Field(
        validation_alias=AliasChoices("size", "Size"),
        description="File size in bytes",
    )
    last_modified: str | None = Field(
        default=None,
        validation_alias=AliasChoices("lastModified", "LastModified"),
        description="Last modification timestamp (ISO format)",
    )
    is_directory: bool = Field(
        default=False,
        validation_alias=AliasChoices("IsDirectory", "isDirectory"),
        description="Whether this entry is a directory",
    )

    @property
    def path(self) -> str:
        """Alias for full_path for consistency."""
        return self.full_path

    @property
    def name(self) -> str:
        """Extract filename from full path."""
        return (
            self.full_path.split("/")[-1] if "/" in self.full_path else self.full_path
        )

class Bucket(BaseModel):
    """Represents a bucket in Orchestrator."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    name: str = Field(alias="Name")
    description: str | None = Field(default=None, alias="Description")
    identifier: str = Field(alias="Identifier")
    storage_provider: str | None = Field(default=None, alias="StorageProvider")
    storage_parameters: str | None = Field(default=None, alias="StorageParameters")
    storage_container: str | None = Field(default=None, alias="StorageContainer")
    options: str | None = Field(default=None, alias="Options")
    credential_store_id: str | None = Field(default=None, alias="CredentialStoreId")
    external_name: str | None = Field(default=None, alias="ExternalName")
    password: str | None = Field(default=None, alias="Password")
    folders_count: int | None = Field(default=None, alias="FoldersCount")
    encrypted: bool | None = Field(default=None, alias="Encrypted")
    id: int | None = Field(default=None, alias="Id")
    tags: list[Any] | None = Field(default=None, alias="Tags")
