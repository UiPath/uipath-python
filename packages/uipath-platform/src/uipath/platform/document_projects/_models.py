"""Pydantic models for the IXP design-time projects resource.

The design-time API serializes with PascalCase keys (``Id``, ``Name``, ...); these
models expose idiomatic snake_case attributes and map to the wire names via field
aliases, so callers work with native Python objects (``project.created_at``) rather
than the raw envelope. ``extra="allow"`` keeps forward compatibility if the API
grows fields before this SDK models them.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    """A design-time project (``GET``/``POST``/``PATCH /api/projects``).

    Mirrors the design-time API ``Project`` contract. ``name`` is the backend slug
    (unique within the tenant) used to address the project in every other call;
    ``title`` is the human-readable display name.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    title: str = Field(alias="Title")
    created_at: datetime = Field(alias="CreatedAt")


class ProjectsPage(BaseModel):
    """A page of projects (``GET /api/projects``).

    ``total`` is the full project count regardless of the window; ``offset`` and
    ``limit`` echo the applied paging window.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    projects: list[Project] = Field(alias="Projects")
    total: int = Field(alias="Total")
    offset: int = Field(alias="Offset")
    limit: int = Field(alias="Limit")


class DeleteProjectResponse(BaseModel):
    """Result of deleting a project (``DELETE /api/projects/{projectName}``).

    A minimal success confirmation; ``status`` is ``"ok"`` on success.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    status: str = Field(alias="Status")
