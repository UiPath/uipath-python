from typing import Any, List, Optional

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
    content_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("contentType", "ContentType"),
        description="MIME type",
    )
    size: int = Field(
        validation_alias=AliasChoices("size", "Size"),
        description="File size in bytes",
    )
    last_modified: Optional[str] = Field(
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
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    name: str = Field(alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    identifier: str = Field(alias="Identifier")
    storage_provider: Optional[str] = Field(default=None, alias="StorageProvider")
    storage_parameters: Optional[str] = Field(default=None, alias="StorageParameters")
    storage_container: Optional[str] = Field(default=None, alias="StorageContainer")
    options: Optional[str] = Field(default=None, alias="Options")
    credential_store_id: Optional[str] = Field(default=None, alias="CredentialStoreId")
    external_name: Optional[str] = Field(default=None, alias="ExternalName")
    password: Optional[str] = Field(default=None, alias="Password")
    folders_count: Optional[int] = Field(default=None, alias="FoldersCount")
    encrypted: Optional[bool] = Field(default=None, alias="Encrypted")
    id: Optional[int] = Field(default=None, alias="Id")
    tags: Optional[List[Any]] = Field(default=None, alias="Tags")
