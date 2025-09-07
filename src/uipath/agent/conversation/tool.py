"""Tool call events."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from .content import InlineOrExternal


class UiPathConversationToolCallResult(BaseModel):
    """Represents the result of a tool call execution."""

    timestamp: Optional[str] = None
    value: Optional[InlineOrExternal] = None
    is_error: Optional[bool] = Field(None, alias="isError")
    cancelled: Optional[bool] = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCall(BaseModel):
    """Represents a call to an external tool or function within a message."""

    tool_call_id: str = Field(..., alias="toolCallId")
    name: str
    arguments: Optional[InlineOrExternal] = None
    timestamp: Optional[str] = None
    result: Optional[UiPathConversationToolCallResult] = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallStartEvent(BaseModel):
    """Signals the start of a tool call."""

    tool_name: str = Field(..., alias="toolName")
    timestamp: Optional[str] = None
    arguments: Optional[InlineOrExternal] = None
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallEndEvent(BaseModel):
    """Signals the end of a tool call."""

    timestamp: Optional[str] = None
    result: Optional[Any] = None
    is_error: Optional[bool] = Field(None, alias="isError")
    cancelled: Optional[bool] = None
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallEvent(BaseModel):
    """Encapsulates the data related to a tool call event."""

    tool_call_id: str = Field(..., alias="toolCallId")
    start: Optional[UiPathConversationToolCallStartEvent] = None
    end: Optional[UiPathConversationToolCallEndEvent] = None
    meta_event: Optional[Dict[str, Any]] = Field(None, alias="metaEvent")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
