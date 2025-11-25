"""Models for LLM Gateway interactions in the UiPath platform."""

from typing import Any, Literal, Union

from pydantic import BaseModel

class EmbeddingItem(BaseModel):
    """Model representing an individual embedding item."""

    embedding: list[float]
    index: int
    object: str

class EmbeddingUsage(BaseModel):
    """Model representing usage statistics for embeddings."""

    prompt_tokens: int
    total_tokens: int

class TextEmbedding(BaseModel):
    """Model representing a text embedding response."""

    data: list[EmbeddingItem]
    model: str
    object: str
    usage: EmbeddingUsage

class ToolCall(BaseModel):
    """Model representing a tool call."""

    id: str
    name: str
    arguments: dict[str, Any]

class ToolPropertyDefinition(BaseModel):
    """Model representing a tool property definition."""

    type: str
    description: str | None = None
    enum: list[str] | None = None

class ToolParametersDefinition(BaseModel):
    """Model representing tool parameters definition."""

    type: str = "object"
    properties: dict[str, ToolPropertyDefinition]
    required: list[str] | None = None

class ToolFunctionDefinition(BaseModel):
    """Model representing a tool function definition."""

    name: str
    description: str | None = None
    parameters: ToolParametersDefinition

class ToolDefinition(BaseModel):
    """Model representing a tool definition."""

    type: Literal["function"] = "function"
    function: ToolFunctionDefinition

class AutoToolChoice(BaseModel):
    """Model representing an automatic tool choice."""

    type: Literal["auto"] = "auto"

class RequiredToolChoice(BaseModel):
    """Model representing a required tool choice."""

    type: Literal["required"] = "required"

class SpecificToolChoice(BaseModel):
    """Model representing a specific tool choice."""

    type: Literal["tool"] = "tool"
    name: str

ToolChoice = Union[
    AutoToolChoice, RequiredToolChoice, SpecificToolChoice, Literal["auto", "none"]
]

class ChatMessage(BaseModel):
    """Model representing a chat message."""

    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None

class ChatCompletionChoice(BaseModel):
    """Model representing a chat completion choice."""

    index: int
    message: ChatMessage
    finish_reason: str

class ChatCompletionUsage(BaseModel):
    """Model representing usage statistics for chat completions."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_read_input_tokens: int | None = None

class ChatCompletion(BaseModel):
    """Model representing a chat completion response."""

    id: str
    object: str
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage
