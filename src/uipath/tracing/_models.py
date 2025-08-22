import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

# class Output:
#     tool_id: Optional[str]
#     content: Optional[str]
#     tool_calls: Optional[list[ToolCall]]
#
# class Usage:
#     promptTokens: int
#     completionTokens: int
#     totalTokens: int
#     isByoExecution: bool
#
# class LLM:
#     invocation_parameters: str
#     provider: str
#     system: str
#     prompts: list[str]]


class Status(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    INTERRUPTED = "INTERRUPTED"


class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class UiPathEvalSpan:
    """Represents a span for evaluation purposes."""

    # llm: Optional[LLM]
    input: dict[str, Any]
    output: Optional[str]
    model: Optional[str]
    # usage: Optional[Usage]
    start_time: datetime
    end_time: datetime
    name: str
    parent_id: str
    id: str
    status: Status
