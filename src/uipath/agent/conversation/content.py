"""Message content part events."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from .citation import UiPathConversationCitation, UiPathConversationCitationEvent


class UiPathConversationContentPartChunkEvent(BaseModel):
    """Contains a chunk of a message content part."""

    content_part_sequence: Optional[int] = Field(None, alias="contentPartSequence")
    data: Optional[str] = None
    citation: Optional[UiPathConversationCitationEvent] = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationContentPartStartEvent(BaseModel):
    """Signals the start of a message content part."""

    mime_type: str = Field(..., alias="mimeType")
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationContentPartEndEvent(BaseModel):
    """Signals the end of a message content part."""

    last_chunk_content_part_sequence: Optional[int] = Field(
        None, alias="lastChunkContentPartSequence"
    )
    interrupted: Optional[Dict[str, Any]] = None
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationContentPartEvent(BaseModel):
    """Encapsulates events related to message content parts."""

    content_part_id: str = Field(..., alias="contentPartId")
    start: Optional[UiPathConversationContentPartStartEvent] = None
    end: Optional[UiPathConversationContentPartEndEvent] = None
    chunk: Optional[UiPathConversationContentPartChunkEvent] = None
    meta_event: Optional[Dict[str, Any]] = Field(None, alias="metaEvent")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathInlineValue(BaseModel):
    """Used when a value is small enough to be returned inline."""

    inline: Any


class UiPathExternalValue(BaseModel):
    """Used when a value is too large to be returned inline."""

    url: str
    byte_count: Optional[int] = Field(None, alias="byteCount")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


InlineOrExternal = Union[UiPathInlineValue, UiPathExternalValue]


class UiPathConversationContentPart(BaseModel):
    """Represents a single part of message content."""

    content_part_id: str = Field(..., alias="contentPartId")
    mime_type: str = Field(..., alias="mimeType")
    data: InlineOrExternal
    citations: Optional[List[UiPathConversationCitation]] = None
    is_transcript: Optional[bool] = Field(None, alias="isTranscript")
    is_incomplete: Optional[bool] = Field(None, alias="isIncomplete")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
