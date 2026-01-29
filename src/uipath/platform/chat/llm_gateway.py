"""Models for LLM Gateway interactions in the UiPath platform."""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel


class EmbeddingItem(BaseModel):
    """Model representing an individual embedding item."""

    embedding: List[float]
    index: int
    object: str


class EmbeddingUsage(BaseModel):
    """Model representing usage statistics for embeddings."""

    prompt_tokens: int
    total_tokens: int


class TextEmbedding(BaseModel):
    """Model representing a text embedding response."""

    data: List[EmbeddingItem]
    model: str
    object: str
    usage: EmbeddingUsage


class ToolCall(BaseModel):
    """Model representing a tool call."""

    id: str
    name: str
    arguments: Dict[str, Any]


class ToolPropertyDefinition(BaseModel):
    """Model representing a tool property definition."""

    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None


class ToolParametersDefinition(BaseModel):
    """Model representing tool parameters definition."""

    type: str = "object"
    properties: Dict[str, ToolPropertyDefinition]
    required: Optional[List[str]] = None


class ToolFunctionDefinition(BaseModel):
    """Model representing a tool function definition."""

    name: str
    description: Optional[str] = None
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
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


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
    cache_read_input_tokens: Optional[int] = None


class ChatCompletion(BaseModel):
    """Model representing a chat completion response."""

    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


class VertexPart(BaseModel):
    """Model representing a part in a Vertex AI response."""

    text: Optional[str] = None


class VertexContent(BaseModel):
    """Model representing content in a Vertex AI response."""

    role: str
    parts: List[VertexPart]


class VertexCandidate(BaseModel):
    """Model representing a candidate in a Vertex AI response."""

    content: VertexContent
    finishReason: Optional[str] = None
    avgLogprobs: Optional[float] = None


class VertexUsageMetadata(BaseModel):
    """Model representing usage metadata in a Vertex AI response."""

    promptTokenCount: Optional[int] = None
    candidatesTokenCount: Optional[int] = None
    totalTokenCount: Optional[int] = None


class VertexCompletion(BaseModel):
    """Model representing a Vertex AI (Gemini) completion response."""

    candidates: List[VertexCandidate]
    usageMetadata: Optional[VertexUsageMetadata] = None
    modelVersion: Optional[str] = None


class BedrockContentBlock(BaseModel):
    """Model representing a content block in a Bedrock response."""

    text: Optional[str] = None


class BedrockMessage(BaseModel):
    """Model representing a message in a Bedrock response."""

    role: str
    content: List[BedrockContentBlock]


class BedrockOutput(BaseModel):
    """Model representing output in a Bedrock response."""

    message: BedrockMessage


class BedrockUsage(BaseModel):
    """Model representing usage statistics in a Bedrock response."""

    inputTokens: Optional[int] = None
    outputTokens: Optional[int] = None
    totalTokens: Optional[int] = None


class BedrockCompletion(BaseModel):
    """Model representing an AWS Bedrock completion response."""

    output: BedrockOutput
    stopReason: Optional[str] = None
    usage: Optional[BedrockUsage] = None
    metrics: Optional[Dict[str, Any]] = None
