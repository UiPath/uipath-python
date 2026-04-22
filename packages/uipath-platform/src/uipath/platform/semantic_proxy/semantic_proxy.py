"""Public Pydantic models for the SemanticProxy service."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PiiDocument(BaseModel):
    """A text document to scan for PII."""

    id: str
    role: str
    document: str


class PiiFile(BaseModel):
    """A file reference to scan for PII."""

    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    file_url: str = Field(alias="fileUrl")
    file_type: str = Field(alias="fileType")


class PiiEntityThreshold(BaseModel):
    """Per-entity confidence threshold override."""

    model_config = ConfigDict(populate_by_name=True)

    category: str = Field(alias="pii-entity-category")
    confidence_threshold: float = Field(alias="pii-entity-confidence-threshold")


class PiiDetectionRequest(BaseModel):
    """Request payload for the PII detection endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    documents: Optional[list[PiiDocument]] = None
    files: Optional[list[PiiFile]] = None
    language_code: Optional[str] = Field(default=None, alias="languageCode")
    confidence_threshold: Optional[float] = Field(
        default=None, alias="confidenceThreshold"
    )
    entity_thresholds: Optional[list[PiiEntityThreshold]] = Field(
        default=None, alias="entityThresholds"
    )


class PiiEntity(BaseModel):
    """A single detected PII entity."""

    model_config = ConfigDict(populate_by_name=True)

    pii_text: str = Field(alias="piiText")
    replacement_text: str = Field(alias="replacementText")
    pii_type: str = Field(alias="piiType")
    offset: int
    confidence_score: float = Field(alias="confidenceScore")


class PiiDocumentResult(BaseModel):
    """PII detection result for a single document."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    role: str
    masked_document: str = Field(alias="maskedDocument")
    initial_document: str = Field(alias="initialDocument")
    pii_entities: list[PiiEntity] = Field(default_factory=list, alias="piiEntities")


class PiiFileResult(BaseModel):
    """PII detection result for a single file (fileUrl is the redacted URL)."""

    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    file_url: str = Field(alias="fileUrl")
    pii_entities: list[PiiEntity] = Field(default_factory=list, alias="piiEntities")


class PiiDetectionResponse(BaseModel):
    """Response payload from the PII detection endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    response: list[PiiDocumentResult] = Field(default_factory=list)
    files: list[PiiFileResult] = Field(default_factory=list)
