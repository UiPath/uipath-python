"""Async input stream events."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .error import UiPathConversationErrorEvent


class UiPathConversationInputStreamChunkEvent(BaseModel):
    """Represents a single chunk of input stream data."""

    data: str

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationAsyncInputStreamStartEvent(BaseModel):
    """Signals the start of an asynchronous input stream."""

    mime_type: str = Field(..., alias="mimeType")
    start_of_speech_sensitivity: str | None = Field(
        None, alias="startOfSpeechSensitivity"
    )
    end_of_speech_sensitivity: str | None = Field(None, alias="endOfSpeechSensitivity")
    prefix_padding_ms: int | None = Field(None, alias="prefixPaddingMs")
    silence_duration_ms: int | None = Field(None, alias="silenceDurationMs")
    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationAsyncInputStreamEndEvent(BaseModel):
    """Signals the end of an asynchronous input stream."""

    metadata: dict[str, Any] | None = Field(None, alias="metaData")
    last_chunk_content_part_sequence: int | None = Field(
        None, alias="lastChunkContentPartSequence"
    )

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationAsyncInputStreamEvent(BaseModel):
    """Encapsulates sub-events related to an asynchronous input stream."""

    stream_id: str = Field(..., alias="streamId")
    start: UiPathConversationAsyncInputStreamStartEvent | None = Field(
        None, alias="startAsyncInputStream"
    )
    end: UiPathConversationAsyncInputStreamEndEvent | None = Field(
        None, alias="endAsyncInputStream"
    )
    chunk: UiPathConversationInputStreamChunkEvent | None = None
    meta_event: dict[str, Any] | None = Field(None, alias="metaEvent")
    error: UiPathConversationErrorEvent | None = Field(
        None, alias="asyncInputStreamError"
    )

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
