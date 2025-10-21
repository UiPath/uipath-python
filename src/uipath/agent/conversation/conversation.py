"""Conversation-level events and capabilities."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UiPathConversationCapabilities(BaseModel):
    """Describes the capabilities of a conversation participant."""

    async_input_stream_emitter: Optional[bool] = Field(
        None, alias="asyncInputStreamEmitter"
    )
    async_input_stream_handler: Optional[bool] = Field(
        None, alias="asyncInputStreamHandler"
    )
    async_tool_call_emitter: Optional[bool] = Field(None, alias="asyncToolCallEmitter")
    async_tool_call_handler: Optional[bool] = Field(None, alias="asyncToolCallHandler")
    mime_types_emitted: Optional[List[str]] = Field(None, alias="mimeTypesEmitted")
    mime_types_handled: Optional[List[str]] = Field(None, alias="mimeTypesHandled")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class UiPathConversationStartEvent(BaseModel):
    """Signals the start of a conversation event stream."""

    capabilities: Optional[UiPathConversationCapabilities] = None
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationStartedEvent(BaseModel):
    """Signals the acceptance of the start of a conversation."""

    capabilities: Optional[UiPathConversationCapabilities] = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationEndEvent(BaseModel):
    """Signals the end of a conversation event stream."""

    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
