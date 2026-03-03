"""Conversation-level events and capabilities."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UiPathSessionCapabilities(BaseModel):
    """Describes the capabilities of a conversation participant."""

    async_input_stream_emitter: bool | None = Field(
        None, alias="asyncInputStreamEmitter"
    )
    async_input_stream_handler: bool | None = Field(
        None, alias="asyncInputStreamHandler"
    )
    async_tool_call_emitter: bool | None = Field(None, alias="asyncToolCallEmitter")
    async_tool_call_handler: bool | None = Field(None, alias="asyncToolCallHandler")
    mime_types_emitted: list[str] | None = Field(None, alias="mimeTypesEmitted")
    mime_types_handled: list[str] | None = Field(None, alias="mimeTypesHandled")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class UiPathSessionStartEvent(BaseModel):
    """Signals the start of session for a conversation."""

    capabilities: UiPathSessionCapabilities | None = None
    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathSessionStartedEvent(BaseModel):
    """Sent in response to a SessionStartEvent to signal the acceptance of the session."""

    capabilities: UiPathSessionCapabilities | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathSessionEndingEvent(BaseModel):
    """Sent by the service when the client needs to end the current session."""

    time_to_live_ms: int = Field(..., alias="timeToLiveMS")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathSessionEndEvent(BaseModel):
    """Signals the end of a session for a conversation."""

    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
