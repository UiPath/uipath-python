"""Citation events for message content."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .error import UiPathConversationErrorEvent


class UiPathConversationCitationStartEvent(BaseModel):
    """Indicates the start of a citation target in a content part."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationCitationEndEvent(BaseModel):
    """Indicates the end of a citation target in a content part."""

    sources: list[UiPathConversationCitationSource]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationCitationEvent(BaseModel):
    """Encapsulates sub-events related to citations."""

    citation_id: str = Field(..., alias="citationId")
    start: UiPathConversationCitationStartEvent | None = Field(
        None, alias="startCitation"
    )
    end: UiPathConversationCitationEndEvent | None = Field(None, alias="endCitation")
    error: UiPathConversationErrorEvent | None = Field(None, alias="citationError")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationCitationSourceBase(BaseModel):
    """Represents a citation source with common base fields."""

    title: str
    number: int

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationCitationSourceUrl(UiPathConversationCitationSourceBase):
    """Represents a citation source that can be rendered as a link (URL)."""

    url: str

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationCitationSourceMedia(UiPathConversationCitationSourceBase):
    """Represents a citation source that references media, such as a PDF document."""

    mime_type: str | None = Field(..., alias="mimeType")
    download_url: str | None = Field(None, alias="downloadUrl")
    page_number: str | None = Field(None, alias="pageNumber")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


UiPathConversationCitationSource = (
    UiPathConversationCitationSourceUrl | UiPathConversationCitationSourceMedia
)


class UiPathConversationCitationData(BaseModel):
    """Represents the core data of a citation or reference inside a content part."""

    offset: int
    length: int
    sources: list[UiPathConversationCitationSource]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationCitation(UiPathConversationCitationData):
    """Represents a citation or reference inside a content part."""

    citation_id: str = Field(..., alias="citationId")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
