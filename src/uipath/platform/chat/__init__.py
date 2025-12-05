"""UiPath Chat Services.

This module provides services for chat-related functionality including:
- LLM Gateway services for chat completions and embeddings
- Conversations service for autopilot conversations
"""

from ._conversations_service import ConversationsService
from ._llm_gateway_service import (
    ChatModels,
    EmbeddingModels,
    UiPathLlmChatService,
    UiPathOpenAIService,
)
from .llm_gateway import (
    AutoToolChoice,
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
)

__all__ = [
    # Conversations Service
    "ConversationsService",
    # LLM Gateway Services
    "ChatModels",
    "EmbeddingModels",
    "UiPathLlmChatService",
    "UiPathOpenAIService",
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
    "EmbeddingItem",
    "EmbeddingUsage",
    "TextEmbedding",
    "ToolChoice",
    "ToolCall",
]
