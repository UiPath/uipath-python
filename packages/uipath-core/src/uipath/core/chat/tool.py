"""Tool call events."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .error import UiPathConversationErrorEvent


class UiPathConversationToolCallResult(BaseModel):
    """Represents the result of a tool call execution."""

    timestamp: str | None = None
    output: Any | None = None
    is_error: bool | None = Field(None, alias="isError")
    cancelled: bool | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallStartEvent(BaseModel):
    """Signals the start of a tool call."""

    tool_name: str = Field(..., alias="toolName")
    timestamp: str | None = None
    input: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallEndEvent(BaseModel):
    """Signals the end of a tool call."""

    timestamp: str | None = None
    output: Any = None
    is_error: bool | None = Field(None, alias="isError")
    cancelled: bool | None = None
    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallEvent(BaseModel):
    """Encapsulates the data related to a tool call event."""

    tool_call_id: str = Field(..., alias="toolCallId")
    start: UiPathConversationToolCallStartEvent | None = Field(
        None, alias="startToolCall"
    )
    end: UiPathConversationToolCallEndEvent | None = Field(None, alias="endToolCall")
    meta_event: dict[str, Any] | None = Field(None, alias="metaEvent")
    error: UiPathConversationErrorEvent | None = Field(None, alias="toolCallError")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallData(BaseModel):
    """Represents the core data of a call to an external tool or function within a message."""

    name: str
    input: dict[str, Any] | None = None
    result: UiPathConversationToolCallResult | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCall(UiPathConversationToolCallData):
    """Represents a call to an external tool or function within a message."""

    tool_call_id: str = Field(..., alias="toolCallId")
    timestamp: str | None = None
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
