"""Async input stream events."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class UiPathConversationInputStreamChunkEvent(BaseModel):
    """Represents a single chunk of input stream data."""

    input_stream_sequence: Optional[int] = Field(None, alias="inputStreamSequence")
    data: str

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationAsyncInputStreamStartEvent(BaseModel):
    """Signals the start of an asynchronous input stream."""

    mime_type: str = Field(..., alias="mimeType")
    start_of_speech_sensitivity: Optional[str] = Field(
        None, alias="startOfSpeechSensitivity"
    )
    end_of_speech_sensitivity: Optional[str] = Field(
        None, alias="endOfSpeechSensitivity"
    )
    prefix_padding_ms: Optional[int] = Field(None, alias="prefixPaddingMs")
    silence_duration_ms: Optional[int] = Field(None, alias="silenceDurationMs")
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationAsyncInputStreamEndEvent(BaseModel):
    """Signals the end of an asynchronous input stream."""

    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")
    last_chunk_content_part_sequence: Optional[int] = Field(
        None, alias="lastChunkContentPartSequence"
    )

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationAsyncInputStreamEvent(BaseModel):
    """Encapsulates sub-events related to an asynchronous input stream."""

    stream_id: str = Field(..., alias="streamId")
    start: Optional[UiPathConversationAsyncInputStreamStartEvent] = None
    end: Optional[UiPathConversationAsyncInputStreamEndEvent] = None
    chunk: Optional[UiPathConversationInputStreamChunkEvent] = None
    meta_event: Optional[Dict[str, Any]] = Field(None, alias="metaEvent")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
