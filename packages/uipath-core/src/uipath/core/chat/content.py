"""Message content part events."""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .citation import (
    UiPathConversationCitation,
    UiPathConversationCitationData,
    UiPathConversationCitationEvent,
)
from .error import UiPathConversationErrorEvent


class UiPathConversationContentPartChunkEvent(BaseModel):
    """Contains a chunk of a message content part."""

    data: str | None = None
    citation: UiPathConversationCitationEvent | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationContentPartStartEvent(BaseModel):
    """Signals the start of a message content part."""

    mime_type: str = Field(..., alias="mimeType")
    metadata: dict[str, Any] | None = Field(None, alias="metaData")
    external_value: UiPathExternalValue | None = Field(None, alias="externalValue")
    name: str | None = None
    timestamp: str | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathContentPartInterrupted(BaseModel):
    """Indicates the interrupt of a content stream."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationContentPartEndEvent(BaseModel):
    """Signals the end of a message content part."""

    last_chunk_content_part_sequence: int | None = Field(
        None, alias="lastChunkContentPartSequence"
    )
    interrupted: UiPathContentPartInterrupted | None = None
    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationContentPartEvent(BaseModel):
    """Encapsulates events related to message content parts."""

    content_part_id: str = Field(..., alias="contentPartId")
    start: UiPathConversationContentPartStartEvent | None = Field(
        None, alias="startContentPart"
    )
    end: UiPathConversationContentPartEndEvent | None = Field(
        None, alias="endContentPart"
    )
    chunk: UiPathConversationContentPartChunkEvent | None = None
    meta_event: dict[str, Any] | None = Field(None, alias="metaEvent")
    error: UiPathConversationErrorEvent | None = Field(None, alias="contentPartError")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathInlineValue(BaseModel):
    """Used when a value is small enough to be returned inline."""

    inline: Any

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathExternalValue(BaseModel):
    """Used when a value is too large to be returned inline."""

    uri: str
    byte_count: int | None = Field(None, alias="byteCount")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


InlineOrExternal = UiPathInlineValue | UiPathExternalValue


class UiPathConversationContentPartData(BaseModel):
    """Represents the core data of a single part of message content."""

    mime_type: str = Field(..., alias="mimeType")
    data: InlineOrExternal
    citations: Sequence[UiPathConversationCitationData]
    is_transcript: bool | None = Field(None, alias="isTranscript")
    is_incomplete: bool | None = Field(None, alias="isIncomplete")
    name: str | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationContentPart(UiPathConversationContentPartData):
    """Represents a single part of message content."""

    content_part_id: str = Field(..., alias="contentPartId")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    # Override to use full type
    citations: Sequence[UiPathConversationCitation]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
