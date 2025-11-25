"""Citation events for message content."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class UiPathConversationCitationStartEvent(BaseModel):
    """Indicates the start of a citation target in a content part."""

    pass

class UiPathConversationCitationEndEvent(BaseModel):
    """Indicates the end of a citation target in a content part."""

    sources: list[dict[str, Any]]

class UiPathConversationCitationEvent(BaseModel):
    """Encapsulates sub-events related to citations."""

    citation_id: str = Field(..., alias="citationId")
    start: UiPathConversationCitationStartEvent | None = None
    end: UiPathConversationCitationEndEvent | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

class UiPathConversationCitationSourceUrl(BaseModel):
    """Represents a citation source that can be rendered as a link (URL)."""

    url: str

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

class UiPathConversationCitationSourceMedia(BaseModel):
    """Represents a citation source that references media, such as a PDF document."""

    mime_type: str = Field(..., alias="mimeType")
    download_url: str | None = Field(None, alias="downloadUrl")
    page_number: str | None = Field(None, alias="pageNumber")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

class UiPathConversationCitationSource(BaseModel):
    """Represents a citation source, either a URL or media reference."""

    title: str | None = None

    # Union of Url or Media
    url: str | None = None
    mime_type: str | None = Field(None, alias="mimeType")
    download_url: str | None = Field(None, alias="downloadUrl")
    page_number: str | None = Field(None, alias="pageNumber")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

class UiPathConversationCitation(BaseModel):
    """Represents a citation or reference inside a content part."""

    citation_id: str = Field(..., alias="citationId")
    offset: int
    length: int
    sources: list[UiPathConversationCitationSource]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
