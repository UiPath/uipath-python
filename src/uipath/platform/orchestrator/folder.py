"""Models for Orchestrator Folders API responses."""

from pydantic import BaseModel, ConfigDict, Field


class PersonalWorkspace(BaseModel):
    """Represents a user's personal workspace folder."""

    model_config = ConfigDict(
        populate_by_name=True,
    )

    fully_qualified_name: str = Field(alias="FullyQualifiedName")
    key: str = Field(alias="Key")
    id: int = Field(alias="Id")
