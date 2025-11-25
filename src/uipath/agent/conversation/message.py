"""Message-level events."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .content import UiPathConversationContentPart, UiPathConversationContentPartEvent
from .tool import UiPathConversationToolCall, UiPathConversationToolCallEvent

class UiPathConversationMessageStartEvent(BaseModel):
    """Signals the start of a message within an exchange."""

    exchange_sequence: int | None = Field(None, alias="exchangeSequence")
    timestamp: str | None = None
    role: str
    meta_data: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

class UiPathConversationMessageEndEvent(BaseModel):
    """Signals the end of a message."""

    meta_data: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

class UiPathConversationMessageEvent(BaseModel):
    """Encapsulates sub-events related to a message."""

    message_id: str = Field(..., alias="messageId")
    start: UiPathConversationMessageStartEvent | None = None
    end: UiPathConversationMessageEndEvent | None = None
    content_part: UiPathConversationContentPartEvent | None = Field(
        None, alias="contentPart"
    )
    tool_call: UiPathConversationToolCallEvent | None = Field(None, alias="toolCall")
    meta_event: dict[str, Any] | None = Field(None, alias="metaEvent")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

class UiPathConversationMessage(BaseModel):
    """Represents a single message within an exchange."""

    message_id: str = Field(..., alias="messageId")
    role: str
    content_parts: list[UiPathConversationContentPart] | None = Field(
        None, alias="contentParts"
    )
    tool_calls: list[UiPathConversationToolCall] | None = Field(
        None, alias="toolCalls"
    )
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
