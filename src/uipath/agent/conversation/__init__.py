"""UiPath Conversation Models.

This module provides Pydantic models that represent the JSON event schema for conversations between a client (UI) and an LLM/agent.

The event objects define a hierarchal conversation structure:

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
    UiPathConversationCitationEndEvent,
    UiPathConversationCitationEvent,
    UiPathConversationCitationSource,
    UiPathConversationCitationSourceMedia,
    UiPathConversationCitationSourceUrl,
    UiPathConversationCitationStartEvent,
)
from .content import (
    UiPathConversationContentPart,
    UiPathConversationContentPartChunkEvent,
    UiPathConversationContentPartEndEvent,
    UiPathConversationContentPartEvent,
    UiPathConversationContentPartStartEvent,
    UiPathExternalValue,
    UiPathInlineValue,
)
from .conversation import (
    UiPathConversationCapabilities,
    UiPathConversationEndEvent,
    UiPathConversationStartedEvent,
    UiPathConversationStartEvent,
)
from .event import UiPathConversationEvent
from .exchange import (
    UiPathConversationExchange,
    UiPathConversationExchangeEndEvent,
    UiPathConversationExchangeEvent,
    UiPathConversationExchangeStartEvent,
)
from .message import (
    UiPathConversationMessage,
    UiPathConversationMessageEndEvent,
    UiPathConversationMessageEvent,
    UiPathConversationMessageStartEvent,
)
from .meta import UiPathConversationMetaEvent
from .tool import (
    UiPathConversationToolCall,
    UiPathConversationToolCallEndEvent,
    UiPathConversationToolCallEvent,
    UiPathConversationToolCallResult,
    UiPathConversationToolCallStartEvent,
)

__all__ = [
    # Root
    "UiPathConversationEvent",
    # Conversation
    "UiPathConversationCapabilities",
    "UiPathConversationStartEvent",
    "UiPathConversationStartedEvent",
    "UiPathConversationEndEvent",
    # Exchange
    "UiPathConversationExchangeStartEvent",
    "UiPathConversationExchangeEndEvent",
    "UiPathConversationExchangeEvent",
    "UiPathConversationExchange",
    # Message
    "UiPathConversationMessageStartEvent",
    "UiPathConversationMessageEndEvent",
    "UiPathConversationMessageEvent",
    "UiPathConversationMessage",
    # Content
    "UiPathConversationContentPartChunkEvent",
    "UiPathConversationContentPartStartEvent",
    "UiPathConversationContentPartEndEvent",
    "UiPathConversationContentPartEvent",
    "UiPathConversationContentPart",
    "UiPathInlineValue",
    "UiPathExternalValue",
    # Citation
    "UiPathConversationCitationStartEvent",
    "UiPathConversationCitationEndEvent",
    "UiPathConversationCitationEvent",
    "UiPathConversationCitationSource",
    "UiPathConversationCitationSourceUrl",
    "UiPathConversationCitationSourceMedia",
    # Tool
    "UiPathConversationToolCallStartEvent",
    "UiPathConversationToolCallEndEvent",
    "UiPathConversationToolCallEvent",
    "UiPathConversationToolCallResult",
    "UiPathConversationToolCall",
    # Async Stream
    "UiPathConversationInputStreamChunkEvent",
    "UiPathConversationAsyncInputStreamStartEvent",
    "UiPathConversationAsyncInputStreamEndEvent",
    "UiPathConversationAsyncInputStreamEvent",
    # Meta
    "UiPathConversationMetaEvent",
]
