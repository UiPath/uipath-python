"""Models for the UiPath Ontology service.

An ontology is a deployed model of a business domain: its objects, properties and
relationships, with a mapping onto Data Fabric entities. The service exposes it by
id (also its key in the Resource Catalog): a details record, the artifact files it
was installed from, a graph view, and a SQL surface over its objects.
"""

import hashlib
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

ONTOLOGY_DEPLOYED_STATE = "DEPLOYED"
"""The state an ontology must be in for the runtime to use it."""


class OntologyDetails(BaseModel):
    """An ontology as the catalog describes it.

    ``name`` is the service identifier the runtime addresses; ``display_name`` is the
    label people know it by in the Resource Catalog.
    """

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    id: str
    name: str
    display_name: Optional[str] = Field(default=None, alias="displayName")
    description: Optional[str] = None
    folder_id: Optional[str] = Field(default=None, alias="folderId")
    state: Optional[str] = None

    @property
    def is_deployed(self) -> bool:
        """Whether the runtime may use this ontology."""
        return self.state == ONTOLOGY_DEPLOYED_STATE


class OntologyArtifact(BaseModel):
    """One file of an ontology, as the artifact manifest lists it.

    ``checksum`` is the SHA-256 of the file's UTF-8 bytes, lower-case hex; a download
    is verified against it and ``size_bytes`` before its content is trusted.
    """

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    file_name: str = Field(alias="fileName")
    type: str
    media_type: str = Field(alias="mediaType")
    size_bytes: int = Field(alias="sizeBytes")
    checksum: str
    created_by: Optional[str] = Field(default=None, alias="createdBy")
    create_time: Optional[str] = Field(default=None, alias="createTime")
    updated_by: Optional[str] = Field(default=None, alias="updatedBy")
    update_time: Optional[str] = Field(default=None, alias="updateTime")


class OntologyArtifactContent(BaseModel):
    """The bytes of one downloaded artifact, with what the response said about them."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_name: str
    content: bytes
    media_type: str
    etag: Optional[str] = None
    type: Optional[str] = None

    @property
    def text(self) -> str:
        """The content decoded as UTF-8, which is how every artifact is stored."""
        return self.content.decode("utf-8")

    def sha256(self) -> str:
        """The lower-case hex SHA-256 of the content, as the manifest records it."""
        return hashlib.sha256(self.content).hexdigest()


class OntologyArtifactIntegrityError(ValueError):
    """A downloaded artifact does not match its manifest entry."""


class SkippedArtifact(BaseModel):
    """A manifest entry ``download_artifacts`` left out, and why."""

    file_name: str
    type: str
    size_bytes: int
    reason: str


class ArtifactDownload(BaseModel):
    """What ``download_artifacts`` fetched and what it skipped.

    ``files`` are verified against the manifest and keep its order. ``skipped`` lists
    the entries over the size cap, so a caller can tell a missing file from one that
    was too large and say so in its trace.
    """

    files: List[OntologyArtifactContent] = Field(default_factory=list)
    skipped: List[SkippedArtifact] = Field(default_factory=list)


class SqlColumn(BaseModel):
    """A column of a SQL answer: its name and the ontology's declared type."""

    model_config = ConfigDict(extra="allow")

    name: str
    type: Optional[str] = None


class SqlResult(BaseModel):
    """The answer to one SELECT over an ontology's objects.

    Rows are objects keyed by column name, as the service writes them. ``row_count``
    is the number of rows in this answer: without a LIMIT the service reads 50, a
    LIMIT is at most 200, and OFFSET reads a later page.
    """

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    columns: List[SqlColumn] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = Field(alias="rowCount")
    generated_sql: Optional[str] = Field(default=None, alias="generatedSql")

    @property
    def column_names(self) -> List[str]:
        """The column names in declared order, or those of the first row."""
        if self.columns:
            return [column.name for column in self.columns]
        return list(self.rows[0].keys()) if self.rows else []
