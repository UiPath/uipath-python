from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict


class Message(BaseModel):
    role: str
    content: str | dict | None = None
    tool_calls: List[ToolCall] | None = None


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict | None = None


class ToolChoice(BaseModel):
    type: str
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    max_tokens: int
    # n: int
    # top_p: float
    temperature: float
    frequency_penalty: float
    presence_penalty: float
    messages: List[Message]
    tools: List[Tool] | None = None
    tool_choice: ToolChoice | None = None
    response_format: Optional[Dict[str, Any]] = None


class ModelSettings(BaseModel):
    top_p: float = 1.0
    n: int = 1
    temperature: float = 0.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: int = 4096
    tool_choice: str | None = None
    enforced_tool_name: str | None = None


class UiPathOutput(BaseModel):
    output_field: str = Field(..., description="The output field")
