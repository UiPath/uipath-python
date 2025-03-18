from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel


class EmbeddingItem(BaseModel):
    embedding: List[float]
    index: int
    object: str


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class TextEmbedding(BaseModel):
    data: List[EmbeddingItem]
    model: str
    object: str
    usage: EmbeddingUsage


class UsageInfo(BaseModel):
    encoding: str
    prompt_tokens: int


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class ToolPropertyDefinition(BaseModel):
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None


class ToolParametersDefinition(BaseModel):
    type: str = "object"
    properties: Dict[str, ToolPropertyDefinition]
    required: Optional[List[str]] = None


class ToolFunctionDefinition(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: ToolParametersDefinition


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: ToolFunctionDefinition


# UiPath normalized API format for tools - matches exactly what the API expects
class UiPathToolDefinition(BaseModel):
    """Tool definition format expected by UiPath LLM Gateway's normalized API."""

    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]

    @classmethod
    def from_tool_definition(cls, tool: ToolDefinition) -> "UiPathToolDefinition":
        """Convert from standard OpenAI tool format to UiPath format."""
        # Create the parameters dictionary in the exact format expected by the API
        parameters = {
            "type": tool.function.parameters.type,
            "properties": {
                name: {
                    "type": prop.type,
                    **({"description": prop.description} if prop.description else {}),
                    **({"enum": prop.enum} if prop.enum else {}),
                }
                for name, prop in tool.function.parameters.properties.items()
            },
        }

        if tool.function.parameters.required:
            parameters["required"] = tool.function.parameters.required

        return cls(
            name=tool.function.name,
            description=tool.function.description,
            parameters=parameters,
        )


class AutoToolChoice(BaseModel):
    type: Literal["auto"] = "auto"


class RequiredToolChoice(BaseModel):
    type: Literal["required"] = "required"


class SpecificToolChoice(BaseModel):
    type: Literal["tool"] = "tool"
    name: str


ToolChoice = Union[
    AutoToolChoice, RequiredToolChoice, SpecificToolChoice, Literal["auto", "none"]
]


class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_read_input_tokens: Optional[int] = None


class ChatCompletion(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage
