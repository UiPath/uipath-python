from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[Any, Any]


class Message(BaseModel):
    role: str
    content: Optional[Union[str, Dict[Any, Any]]] = None
    tool_calls: Optional[List[ToolCall]] = None


class Tool(BaseModel):
    name: str
    description: str
    parameters: Optional[Dict[Any, Any]] = None


class ToolChoice(BaseModel):
    type: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    max_tokens: int
    # n: int
    # top_p: float
    temperature: float
    frequency_penalty: float
    presence_penalty: float
    messages: List[Message]
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[ToolChoice] = None
    response_format: Optional[Dict[str, Any]] = None


class ModelSettings(BaseModel):
    top_p: float = 1.0
    n: int = 1
    temperature: float = 0.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: int = 4096
    tool_choice: Optional[str] = None
    enforced_tool_name: Optional[str] = None


class UiPathOutput(BaseModel):
    output_field: str = Field(..., description="The output field")
