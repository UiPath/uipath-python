"""Message-level events."""

from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .content import (
    UiPathConversationContentPart,
    UiPathConversationContentPartData,
    UiPathConversationContentPartEvent,
)
from .error import UiPathConversationErrorEvent
from .interrupt import (
    UiPathConversationInterrupt,
    UiPathConversationInterruptData,
    UiPathConversationInterruptEvent,
)
from .tool import (
    UiPathConversationToolCall,
    UiPathConversationToolCallData,
    UiPathConversationToolCallEvent,
)


class UiPathConversationMessageStartEvent(BaseModel):
    """Signals the start of a message within an exchange."""

    exchange_sequence: int | None = Field(None, alias="exchangeSequence")
    timestamp: str | None = None
    role: str
    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationMessageEndEvent(BaseModel):
    """Signals the end of a message."""

    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationMessageEvent(BaseModel):
    """Encapsulates sub-events related to a message."""

    message_id: str = Field(..., alias="messageId")
    start: UiPathConversationMessageStartEvent | None = Field(
        None, alias="startMessage"
    )
    end: UiPathConversationMessageEndEvent | None = Field(None, alias="endMessage")
    content_part: UiPathConversationContentPartEvent | None = Field(
        None, alias="contentPart"
    )
    tool_call: UiPathConversationToolCallEvent | None = Field(None, alias="toolCall")
    interrupt: UiPathConversationInterruptEvent | None = None
    meta_event: dict[str, Any] | None = Field(None, alias="metaEvent")
    error: UiPathConversationErrorEvent | None = Field(None, alias="messageError")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationMessageData(BaseModel):
    """Represents the core data of a single message within an exchange."""

    role: str
    content_parts: Sequence[UiPathConversationContentPartData] = Field(
        ..., alias="contentParts"
    )
    tool_calls: Sequence[UiPathConversationToolCallData] = Field(..., alias="toolCalls")
    interrupts: Sequence[UiPathConversationInterruptData]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationMessage(UiPathConversationMessageData):
    """Represents a single message within an exchange."""

    message_id: str = Field(..., alias="messageId")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    span_id: str | None = Field(None, alias="spanId")

    # Overrides to use full types
    content_parts: Sequence[UiPathConversationContentPart] = Field(
        ..., alias="contentParts"
    )
    tool_calls: Sequence[UiPathConversationToolCall] = Field(..., alias="toolCalls")
    interrupts: Sequence[UiPathConversationInterrupt]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
