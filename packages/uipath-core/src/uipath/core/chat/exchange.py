"""Exchange-level events.

Characteristics of an Exchange:
It groups together messages that belong to the same turn of conversation.

Example:
    User says something → one message inside the exchange.
    LLM responds → one or more messages in the same exchange.

Each exchange has:
    A start event (signals the beginning of the turn).
    An end event (signals the end of the turn).
    Messages that happened in between.

An exchange can include multiple messages (e.g. LLM streaming several outputs, or user message + assistant + tool outputs).
Exchanges are ordered within a conversation via conversation_sequence.
"""

from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .error import UiPathConversationErrorEvent
from .message import (
    UiPathConversationMessage,
    UiPathConversationMessageData,
    UiPathConversationMessageEvent,
)


class UiPathConversationExchangeStartEvent(BaseModel):
    """Signals the start of an exchange of messages within a conversation."""

    conversation_sequence: int | None = Field(None, alias="conversationSequence")
    metadata: dict[str, Any] | None = Field(None, alias="metaData")
    timestamp: str | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationExchangeEndEvent(BaseModel):
    """Signals the end of an exchange of messages within a conversation."""

    metadata: dict[str, Any] | None = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationExchangeEvent(BaseModel):
    """Encapsulates a single exchange in the conversation."""

    exchange_id: str = Field(..., alias="exchangeId")
    start: UiPathConversationExchangeStartEvent | None = Field(
        None, alias="startExchange"
    )
    end: UiPathConversationExchangeEndEvent | None = Field(None, alias="endExchange")
    message: UiPathConversationMessageEvent | None = None
    meta_event: dict[str, Any] | None = Field(None, alias="metaEvent")
    error: UiPathConversationErrorEvent | None = Field(None, alias="exchangeError")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationExchangeData(BaseModel):
    """Represents the core data of a group of related messages (one turn of conversation)."""

    messages: Sequence[UiPathConversationMessageData]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationExchange(UiPathConversationExchangeData):
    """Represents a group of related messages (one turn of conversation)."""

    exchange_id: str = Field(..., alias="exchangeId")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    span_id: str | None = Field(None, alias="spanId")

    # Override to use full type
    messages: Sequence[UiPathConversationMessage]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
