"""UiPath Chat Services.

This module provides services for chat-related functionality including:
- LLM Gateway services for chat completions and embeddings
- Conversations service for autopilot conversations
"""

from ._conversations_service import ConversationsService
from ._llm_gateway_service import (
    APIFlavor,
    BedrockModels,
    ChatModels,
    EmbeddingModels,
    GeminiModels,
    UiPathBedrockService,
    UiPathLlmChatService,
    UiPathOpenAIService,
    UiPathVertexService,
)
from .llm_gateway import (
    AutoToolChoice,
    BedrockCompletion,
    ChatCompletion,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatMessage,
    EmbeddingItem,
    EmbeddingUsage,
    RequiredToolChoice,
    SpecificToolChoice,
    TextEmbedding,
    ToolCall,
    ToolChoice,
    ToolDefinition,
    ToolFunctionDefinition,
    ToolParametersDefinition,
    ToolPropertyDefinition,
    VertexCompletion,
)
from .llm_throttle import get_llm_semaphore, set_llm_concurrency

__all__ = [
    # Conversations Service
    "ConversationsService",
    # LLM Gateway Services
    "APIFlavor",
    "BedrockModels",
    "ChatModels",
    "EmbeddingModels",
    "GeminiModels",
    "UiPathBedrockService",
    "UiPathLlmChatService",
    "UiPathOpenAIService",
    "UiPathVertexService",
    # LLM Throttling
    "get_llm_semaphore",
    "set_llm_concurrency",
    # LLM Gateway Models
    "ToolPropertyDefinition",
    "ToolParametersDefinition",
    "ToolFunctionDefinition",
    "ToolDefinition",
    "AutoToolChoice",
    "RequiredToolChoice",
    "SpecificToolChoice",
    "ChatMessage",
    "ChatCompletionChoice",
    "ChatCompletionUsage",
    "ChatCompletion",
    "VertexCompletion",
    "BedrockCompletion",
    "EmbeddingItem",
    "EmbeddingUsage",
    "TextEmbedding",
    "ToolChoice",
    "ToolCall",
]
