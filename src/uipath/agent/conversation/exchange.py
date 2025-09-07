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

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .message import UiPathConversationMessage, UiPathConversationMessageEvent


class UiPathConversationExchangeStartEvent(BaseModel):
    """Signals the start of an exchange of messages within a conversation."""

    conversation_sequence: Optional[int] = Field(None, alias="conversationSequence")
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationExchangeEndEvent(BaseModel):
    """Signals the end of an exchange of messages within a conversation."""

    meta_data: Optional[Dict[str, Any]] = Field(None, alias="metaData")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationExchangeEvent(BaseModel):
    """Encapsulates a single exchange in the conversation."""

    exchange_id: str = Field(..., alias="exchangeId")
    start: Optional[UiPathConversationExchangeStartEvent] = None
    end: Optional[UiPathConversationExchangeEndEvent] = None
    message: Optional[UiPathConversationMessageEvent] = None
    meta_event: Optional[Dict[str, Any]] = Field(None, alias="metaEvent")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationExchange(BaseModel):
    """Represents a group of related messages (one turn of conversation)."""

    exchange_id: str = Field(..., alias="exchangeId")
    messages: List[UiPathConversationMessage]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
