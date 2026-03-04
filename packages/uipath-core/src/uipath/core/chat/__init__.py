"""UiPath Conversation Models.

This module provides Pydantic models that represent the JSON event schema for conversations between a client (UI) and an LLM/agent.

The event objects define a hierarchical conversation structure:

* Conversation
    * Exchange
        * Message
            * Content Parts
                * Citations
            * Tool Calls
                * Tool Results

 A conversation may contain multiple exchanges, and an exchange may contain multiple messages. A message may contain
 multiple content parts, each of which can be text or binary, including media input and output streams; and each
 content part can include multiple citations. A message may also contain multiple tool calls, which may contain a tool
 result.

 The protocol also supports a top level, "async", input media streams (audio and video), which can span multiple
 exchanges. These are used for Gemini's automatic turn detection mode, where the LLM determines when the user has
 stopped talking and starts producing output. The output forms one or more messages in an exchange with no explicit
 input message. However, the LLM may produce an input transcript which can be used to construct the implicit input
 message that started the exchange.

 In addition, the protocol also supports "async" tool calls that span multiple exchanges. This can be used with
 Gemini's asynchronous function calling protocol, which allows function calls to produce results that interrupt the
 conversation when ready, even after multiple exchanges. They also support generating multiple results from a single
 tool call. By contrast most tool calls are scoped to a single message, which contains both the call and the single
 result produced by that call.

 Not all features supported by the protocol will be supported by all clients and LLMs. The optional top level
 `capabilities` property can be used to communicate information about supported features. This property should be set
 on the first event written to a new websocket connection. This initial event may or may not contain additional
 sub-events.
"""

from .async_stream import (
    UiPathConversationAsyncInputStreamEndEvent,
    UiPathConversationAsyncInputStreamEvent,
    UiPathConversationAsyncInputStreamStartEvent,
    UiPathConversationInputStreamChunkEvent,
)
from .citation import (
    UiPathConversationCitation,
    UiPathConversationCitationData,
    UiPathConversationCitationEndEvent,
    UiPathConversationCitationEvent,
    UiPathConversationCitationSource,
    UiPathConversationCitationSourceBase,
    UiPathConversationCitationSourceMedia,
    UiPathConversationCitationSourceUrl,
    UiPathConversationCitationStartEvent,
)
from .content import (
    InlineOrExternal,
    UiPathContentPartInterrupted,
    UiPathConversationContentPart,
    UiPathConversationContentPartChunkEvent,
    UiPathConversationContentPartData,
    UiPathConversationContentPartEndEvent,
    UiPathConversationContentPartEvent,
    UiPathConversationContentPartStartEvent,
    UiPathExternalValue,
    UiPathInlineValue,
)
from .error import (
    UiPathConversationErrorEndEvent,
    UiPathConversationErrorEvent,
    UiPathConversationErrorStartEvent,
)
from .event import UiPathConversationEvent, UiPathConversationLabelUpdatedEvent
from .exchange import (
    UiPathConversationExchange,
    UiPathConversationExchangeData,
    UiPathConversationExchangeEndEvent,
    UiPathConversationExchangeEvent,
    UiPathConversationExchangeStartEvent,
)
from .interrupt import (
    InterruptTypeEnum,
    UiPathConversationGenericInterruptEndEvent,
    UiPathConversationGenericInterruptStartEvent,
    UiPathConversationInterrupt,
    UiPathConversationInterruptData,
    UiPathConversationInterruptEndEvent,
    UiPathConversationInterruptEvent,
    UiPathConversationInterruptStartEvent,
    UiPathConversationToolCallConfirmationEndValue,
    UiPathConversationToolCallConfirmationInterruptEndEvent,
    UiPathConversationToolCallConfirmationInterruptStartEvent,
    UiPathConversationToolCallConfirmationValue,
)
from .message import (
    UiPathConversationMessage,
    UiPathConversationMessageData,
    UiPathConversationMessageEndEvent,
    UiPathConversationMessageEvent,
    UiPathConversationMessageStartEvent,
)
from .meta import UiPathConversationMetaEvent
from .session import (
    UiPathSessionCapabilities,
    UiPathSessionEndEvent,
    UiPathSessionEndingEvent,
    UiPathSessionStartedEvent,
    UiPathSessionStartEvent,
)
from .tool import (
    UiPathConversationToolCall,
    UiPathConversationToolCallData,
    UiPathConversationToolCallEndEvent,
    UiPathConversationToolCallEvent,
    UiPathConversationToolCallResult,
    UiPathConversationToolCallStartEvent,
)

__all__ = [
    # Root
    "UiPathConversationEvent",
    "UiPathConversationLabelUpdatedEvent",
    # Error
    "UiPathConversationErrorStartEvent",
    "UiPathConversationErrorEndEvent",
    "UiPathConversationErrorEvent",
    # Session
    "UiPathSessionCapabilities",
    "UiPathSessionStartEvent",
    "UiPathSessionStartedEvent",
    "UiPathSessionEndingEvent",
    "UiPathSessionEndEvent",
    # Exchange
    "UiPathConversationExchangeStartEvent",
    "UiPathConversationExchangeEndEvent",
    "UiPathConversationExchangeEvent",
    "UiPathConversationExchangeData",
    "UiPathConversationExchange",
    # Message
    "UiPathConversationMessageStartEvent",
    "UiPathConversationMessageEndEvent",
    "UiPathConversationMessageEvent",
    "UiPathConversationMessageData",
    "UiPathConversationMessage",
    # Interrupt
    "InterruptTypeEnum",
    "UiPathConversationInterruptStartEvent",
    "UiPathConversationInterruptEndEvent",
    "UiPathConversationInterruptEvent",
    "UiPathConversationToolCallConfirmationValue",
    "UiPathConversationToolCallConfirmationEndValue",
    "UiPathConversationToolCallConfirmationInterruptStartEvent",
    "UiPathConversationToolCallConfirmationInterruptEndEvent",
    "UiPathConversationGenericInterruptStartEvent",
    "UiPathConversationGenericInterruptEndEvent",
    "UiPathConversationInterruptData",
    "UiPathConversationInterrupt",
    # Content
    "UiPathConversationContentPartChunkEvent",
    "UiPathConversationContentPartStartEvent",
    "UiPathContentPartInterrupted",
    "UiPathConversationContentPartEndEvent",
    "UiPathConversationContentPartEvent",
    "UiPathConversationContentPartData",
    "UiPathConversationContentPart",
    "UiPathInlineValue",
    "UiPathExternalValue",
    "InlineOrExternal",
    # Citation
    "UiPathConversationCitationStartEvent",
    "UiPathConversationCitationEndEvent",
    "UiPathConversationCitationEvent",
    "UiPathConversationCitationSourceBase",
    "UiPathConversationCitationSourceUrl",
    "UiPathConversationCitationSourceMedia",
    "UiPathConversationCitationSource",
    "UiPathConversationCitationData",
    "UiPathConversationCitation",
    # Tool
    "UiPathConversationToolCallStartEvent",
    "UiPathConversationToolCallEndEvent",
    "UiPathConversationToolCallEvent",
    "UiPathConversationToolCallResult",
    "UiPathConversationToolCallData",
    "UiPathConversationToolCall",
    # Async Stream
    "UiPathConversationInputStreamChunkEvent",
    "UiPathConversationAsyncInputStreamStartEvent",
    "UiPathConversationAsyncInputStreamEndEvent",
    "UiPathConversationAsyncInputStreamEvent",
    # Meta
    "UiPathConversationMetaEvent",
]
