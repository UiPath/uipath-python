"""Models for VDBS Skills API responses."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SkillVersionStatus(str, Enum):
    """Lifecycle status of a skill version.

    The BE serializes this as a PascalCase string (e.g. ``"Published"``) on
    OData reads — not the underlying integer.
    """

    DRAFT = "Draft"
    PUBLISHED = "Published"
    DEPRECATED = "Deprecated"
    RETIRED = "Retired"


class VersionBumpLevel(str, Enum):
    """Semver bump level requested when creating a new skill version."""

    MAJOR = "Major"
    MINOR = "Minor"
    PATCH = "Patch"


class SkillVersionSummary(BaseModel):
    """Lightweight summary of a skill version, embedded on Skill responses."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    id: str = Field(alias="id")
    version: str = Field(alias="version")
    status: SkillVersionStatus = Field(alias="status")
    published_at: Optional[datetime] = Field(default=None, alias="publishedAt")
    created_date: datetime = Field(alias="createdDate")


class SkillVersion(BaseModel):
    """A versioned snapshot of a skill's content."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    id: str = Field(alias="id")
    skill_id: str = Field(alias="skillId")
    version: str = Field(alias="version")
    content: Optional[str] = Field(default=None, alias="content")
    status: SkillVersionStatus = Field(alias="status")
    published_at: Optional[datetime] = Field(default=None, alias="publishedAt")
    deprecated_at: Optional[datetime] = Field(default=None, alias="deprecatedAt")
    retired_at: Optional[datetime] = Field(default=None, alias="retiredAt")
    created_date: datetime = Field(alias="createdDate")


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

    id: str = Field(alias="id")
    name: str = Field(alias="name")
    description: Optional[str] = Field(default=None, alias="description")
    grace_period_days: int = Field(alias="gracePeriodDays")
    created_date: datetime = Field(alias="createdDate")
    last_updated_date: datetime = Field(alias="lastUpdatedDate")
    folder_key: str = Field(alias="folderKey")
    published_version: Optional[SkillVersionSummary] = Field(
        default=None, alias="publishedVersion"
    )
    current_draft: Optional[SkillVersionSummary] = Field(
        default=None, alias="currentDraft"
    )
    versions: List[SkillVersion] = Field(default_factory=list, alias="versions")
    tags: List[str] = Field(default_factory=list, alias="tags")
