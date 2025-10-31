"""Folder models for UiPath Orchestrator."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Folder(BaseModel):
    """Folder model for organizational structure."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    id: Optional[int] = Field(None, alias="Id", description="Folder ID")
    key: Optional[str] = Field(None, alias="Key", description="Folder UUID key")
    display_name: str = Field(
        ..., alias="DisplayName", description="Folder display name"
    )
    fully_qualified_name: Optional[str] = Field(
        None,
        alias="FullyQualifiedName",
        description="Full path of the folder (e.g., 'Shared/Finance')",
    )
    description: Optional[str] = Field(
        None, alias="Description", description="Folder description"
    )
    parent_id: Optional[int] = Field(
        None, alias="ParentId", description="Parent folder ID"
    )
    feed_type: Optional[str] = Field(
        None,
        alias="FeedType",
        description="Feed type (e.g., 'Personal', 'DirectoryService')",
    )
