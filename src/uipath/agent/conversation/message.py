"""Message-level events."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .content import UiPathConversationContentPart, UiPathConversationContentPartEvent
from .tool import UiPathConversationToolCall, UiPathConversationToolCallEvent


class UiPathConversationMessageStartEvent(BaseModel):
    """Signals the start of a message within an exchange."""

    exchange_sequence: Optional[int] = Field(None, alias="exchangeSequence")
    timestamp: Optional[str] = None
    role: str
    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationMessageEndEvent(BaseModel):
    """Signals the end of a message."""

    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationMessageEvent(BaseModel):
    """Encapsulates sub-events related to a message."""

    message_id: str = Field(..., alias="messageId")
    start: Optional[UiPathConversationMessageStartEvent] = None
    end: Optional[UiPathConversationMessageEndEvent] = None
    content_part: Optional[UiPathConversationContentPartEvent] = Field(
        None, alias="contentPart"
    )
    tool_call: Optional[UiPathConversationToolCallEvent] = Field(None, alias="toolCall")
    meta_event: Optional[Dict[str, Any]] = Field(None, alias="metaEvent")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationMessage(BaseModel):
    """Represents a single message within an exchange."""

    message_id: str = Field(..., alias="messageId")
    role: str
    content_parts: Optional[List[UiPathConversationContentPart]] = Field(
        None, alias="contentParts"
    )
    tool_calls: Optional[List[UiPathConversationToolCall]] = Field(
        None, alias="toolCalls"
    )
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
