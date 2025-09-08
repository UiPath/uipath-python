"""The top-level event type representing an event in a conversation.

This is the root container for all other event subtypes (conversation start,
exchanges, messages, content, citations, tool calls, and async streams).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .async_stream import UiPathConversationAsyncInputStreamEvent
from .conversation import (
    UiPathConversationEndEvent,
    UiPathConversationStartedEvent,
    UiPathConversationStartEvent,
)
from .exchange import UiPathConversationExchangeEvent
from .meta import UiPathConversationMetaEvent
from .tool import UiPathConversationToolCallEvent


class UiPathConversationEvent(BaseModel):
    """The top-level event type representing an event in a conversation.

    This is the root container for all other event subtypes (conversation start,
    exchanges, messages, content, citations, tool calls, and async streams).
    """

    """A globally unique identifier for conversation to which the other sub-event and data properties apply."""
    conversation_id: str = Field(..., alias="conversationId")
    """Signals the start of an event stream concerning a conversation. This event does NOT necessarily mean this is a
    brand new conversation. It may be a continuation of an existing conversation.
    """
    start: Optional[UiPathConversationStartEvent] = None
    """Signals the acceptance of the start of a conversation."""
    started: Optional[UiPathConversationStartedEvent] = None
    """Signals the end of a conversation event stream. This does NOT mean the conversation is over. A new event stream for
    the conversation could be started in the future.
    """
    end: Optional[UiPathConversationEndEvent] = None
    """Encapsulates sub-events related to an exchange within a conversation."""
    exchange: Optional[UiPathConversationExchangeEvent] = None
    """Encapsulates sub-events related to an asynchronous input stream."""
    async_input_stream: Optional[UiPathConversationAsyncInputStreamEvent] = Field(
        None, alias="asyncInputStream"
    )
    """Optional async tool call sub-event. This feature is not supported by all LLMs. Most tool calls are scoped to a
    message, and use the toolCall and toolResult properties defined by the ConversationMessage type.
    """
    async_tool_call: Optional[UiPathConversationToolCallEvent] = Field(
        None, alias="asyncToolCall"
    )
    """Allows additional events to be sent in the context of the enclosing event stream."""
    meta_event: Optional[UiPathConversationMetaEvent] = Field(None, alias="metaEvent")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
