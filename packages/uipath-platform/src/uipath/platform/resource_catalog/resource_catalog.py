"""Models for Resource Catalog service."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResourceType(str, Enum):
    """Resource type."""

    ASSET = "asset"
    BUCKET = "bucket"
    MACHINE = "machine"
    TRIGGER = "trigger"
    PROCESS = "process"
    PACKAGE = "package"
    LIBRARY = "library"
    INDEX = "index"
    APP = "app"
    CONNECTION = "connection"
    CONNECTOR = "connector"
    MCP_SERVER = "mcpserver"
    QUEUE = "queue"

    @classmethod
    def from_string(cls, value: str) -> "ResourceType":
        """Create a ResourceType instance from a string value.

        Args:
            value: String value to convert to ResourceType

        Returns:
            ResourceType: The matching ResourceType enum member

        Raises:
            ValueError: If the value doesn't match any ResourceType
        """
        lower_value = value.lower()
        for member in cls:
            if member.value == lower_value:
                return member

        available = ", ".join([f"'{member.value}'" for member in cls])
        raise ValueError(
            f"'{value}' is not a valid ResourceType. Available options: {available}"
        )


class Tag(BaseModel):
    """Tag model for resources."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    key: str
    display_name: str = Field(alias="displayName")
    name: str
    display_value: str = Field(alias="displayValue")
    value: str
    type: str
    account_key: str = Field(alias="accountKey")
    tenant_key: Optional[str] = Field(None, alias="tenantKey")
    user_key: Optional[str] = Field(None, alias="userKey")


class Folder(BaseModel):
    """Folder model for resources."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    id: int
    key: str
    display_name: str = Field(alias="displayName")
    code: str
    fully_qualified_name: str = Field(alias="fullyQualifiedName")
    timestamp: str
    tenant_key: str = Field(alias="tenantKey")
    account_key: str = Field(alias="accountKey")
    user_key: Optional[str] = Field(None, alias="userKey")
    type: str
    path: str
    permissions: Optional[List[str]] = Field(default_factory=list)


class Resource(BaseModel):
    """Resource model from Resource Catalog."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    resource_key: str = Field(alias="entityKey")
    name: str
    description: Optional[str] = None
    resource_type: str = Field(alias="entityType")
    tags: Optional[List[Tag]] = Field(default_factory=list)
    folders: List[Folder] = Field(default_factory=list)
    linked_folders_count: int = Field(0, alias="linkedFoldersCount")
    source: Optional[str] = None
    scope: str
    search_state: str = Field(alias="searchState")
    timestamp: str
    folder_key: Optional[str] = Field(None, alias="folderKey")
    folder_keys: List[str] = Field(default_factory=list, alias="folderKeys")
    tenant_key: Optional[str] = Field(None, alias="tenantKey")
    account_key: str = Field(alias="accountKey")
    user_key: Optional[str] = Field(None, alias="userKey")
    dependencies: Optional[list[str]] = Field(default_factory=list)
    custom_data: Optional[str] = Field(None, alias="customData")
    resource_sub_type: Optional[str] = Field(None, alias="entitySubType")


class ResourceSearchResponse(BaseModel):
    """Response model for resource search API."""

    count: int
    value: List[Resource]
