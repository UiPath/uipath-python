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


class UiPathVoiceToolDescriptor(_VoiceWire):
    """A tool the runtime registered for a voice session.

    CAS names the tools it offers the voice model itself, then matches each one to
    ``name`` by its agent-definition resource (and, for MCP, the server's tool name)
    before dispatching a call, so ``name`` never has to be predicted on the CAS side.
    """

    name: str
    resource_name: str = Field(..., alias="resourceName")
    mcp_tool_name: str | None = Field(None, alias="mcpToolName")


class UiPathVoiceToolsReady(_VoiceWire):
    """Payload of ``voice_tools_ready``: the tools this runtime can execute."""

    tools: list[UiPathVoiceToolDescriptor] = Field(default_factory=list)
