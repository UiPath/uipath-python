"""Models for VDBS Skills API responses."""

from datetime import datetime
from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SkillVersionStatus(IntEnum):
    """Lifecycle status of a skill version.

    Matches the C# SkillVersionStatus enum on the VDBS backend.
    """

    DRAFT = 0
    PUBLISHED = 1
    DEPRECATED = 2
    RETIRED = 3


class VersionBumpLevel(IntEnum):
    """Semver bump level requested when creating a new skill version.

    Matches the C# VersionBumpLevel enum on the VDBS backend.
    """

    MAJOR = 0
    MINOR = 1
    PATCH = 2


class SkillVersionSummary(BaseModel):
    """Lightweight summary of a skill version, embedded on Skill responses."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    id: str = Field(alias="Id")
    version: str = Field(alias="Version")
    status: SkillVersionStatus = Field(alias="Status")
    published_at: Optional[datetime] = Field(default=None, alias="PublishedAt")
    created_date: datetime = Field(alias="CreatedDate")


class SkillVersion(BaseModel):
    """A versioned snapshot of a skill's content."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    id: str = Field(alias="Id")
    skill_id: str = Field(alias="SkillId")
    version: str = Field(alias="Version")
    content: Optional[str] = Field(default=None, alias="Content")
    status: SkillVersionStatus = Field(alias="Status")
    published_at: Optional[datetime] = Field(default=None, alias="PublishedAt")
    deprecated_at: Optional[datetime] = Field(default=None, alias="DeprecatedAt")
    retired_at: Optional[datetime] = Field(default=None, alias="RetiredAt")
    created_date: datetime = Field(alias="CreatedDate")


class Skill(BaseModel):
    """A named, versioned, folder-scoped skill resource.

    The published version's content is the prompt an agent uses when invoking
    this skill as a tool. Drafts are mutable; published versions are immutable.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    grace_period_days: int = Field(alias="GracePeriodDays")
    created_date: datetime = Field(alias="CreatedDate")
    last_updated_date: datetime = Field(alias="LastUpdatedDate")
    folder_key: str = Field(alias="FolderKey")
    published_version: Optional[SkillVersionSummary] = Field(
        default=None, alias="PublishedVersion"
    )
    current_draft: Optional[SkillVersionSummary] = Field(
        default=None, alias="CurrentDraft"
    )
    versions: List[SkillVersion] = Field(default_factory=list, alias="Versions")
    tags: List[str] = Field(default_factory=list, alias="Tags")
