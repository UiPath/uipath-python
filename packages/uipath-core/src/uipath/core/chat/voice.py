"""Voice tool-call wire models (CAS socket.io)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _VoiceWire(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathVoiceToolCallRequest(_VoiceWire):
    """Single tool call in a batch."""

    call_id: str = Field(..., alias="callId")
    tool_name: str = Field(..., alias="toolName")
    args: dict[str, Any]


class UiPathVoiceToolCallMessage(_VoiceWire):
    """Batch of tool calls from CAS."""

    calls: list[UiPathVoiceToolCallRequest] = Field(..., min_length=1)


class UiPathVoiceToolCallResult(_VoiceWire):
    """Result of a single tool call."""

    result: str
    is_error: bool = Field(..., alias="isError")
