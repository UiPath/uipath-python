"""Agent model definition."""

from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from uipath.models import Connection


class ToolType(str, Enum):
    """Type of tool."""

    INTEGRATION = "INTEGRATION"
    ESCALATION = "ESCALATION"
    AGENT = "AGENT"
    # TODO: Process/Action?


class BaseToolDefinition(BaseModel):
    """Base tool definition."""

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    resource_type: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class IntegrationToolProperties(BaseModel):
    """Integration tool properties."""

    tool_path: str = Field(..., alias="toolPath")
    object_name: str = Field(..., alias="objectName")
    tool_display_name: str = Field(..., alias="toolDisplayName")
    tool_description: str = Field(..., alias="toolDescription")
    method: str = Field(..., alias="method")
    body_structure: dict[str, str] = Field(..., alias="bodyStructure")  # TODO
    connection: Connection = Field(..., alias="connection")
    parameters: list[dict[str, Any]] = Field(..., alias="parameters")


class IntegrationToolDefinition(BaseToolDefinition):
    """Integration tool definition."""

    type: Literal[ToolType.INTEGRATION] = ToolType.INTEGRATION
    properties: IntegrationToolProperties


class EscalationChannelProperties(BaseModel):
    """Escalation channel properties."""

    app_name: str = Field(..., alias="appName")
    app_version: str = Field(..., alias="appVersion")
    folder_name: Optional[str] = Field(..., alias="folderName")
    resource_key: str = Field(..., alias="resourceKey")
    is_actionable_message_enabled: bool = Field(..., alias="isActionableMessageEnabled")
    actionable_message_meta_data: Optional[dict[str, Any]] = Field(
        ..., alias="actionableMessageMetaData"
    )


class EscalationChannel(BaseModel):
    """Escalation channel."""

    id: str = Field(..., alias="id")
    type: str = Field(..., alias="type")
    name: str = Field(..., alias="name")
    input_schema: dict[str, Any] = Field(..., alias="inputSchema")
    output_schema: dict[str, Any] = Field(..., alias="outputSchema")
    recipients: list[dict[str, Any]] = Field(..., alias="recipients")  # TODO
    properties: EscalationChannelProperties = Field(..., alias="properties")


class EscalationToolProperties(BaseModel):
    """Escalation tool properties."""

    type: int = Field(..., alias="type")
    channels: list[EscalationChannel] = Field(..., alias="channels")


class EscalationToolDefinition(BaseToolDefinition):
    """Escalation tool definition."""

    type: Literal[ToolType.ESCALATION] = ToolType.ESCALATION
    properties: EscalationToolProperties


class AgentToolProperties(BaseModel):
    """Agent tool properties."""

    process_name: str = Field(..., alias="processName")
    folder_path: str = Field(..., alias="folderPath")


class AgentToolDefinition(BaseToolDefinition):
    """Agent tool definition."""

    type: Literal[ToolType.AGENT] = ToolType.AGENT
    properties: AgentToolProperties


ToolDefinition = Annotated[
    Union[IntegrationToolDefinition, EscalationToolDefinition, AgentToolDefinition],
    Field(discriminator="type"),
]


class AgentDefinition(BaseModel):
    """Agent definition."""

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    name: str = Field(..., description="The name of the agent")
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tools: list[ToolDefinition]


class LowCodeAgentDefinition(AgentDefinition):
    """Low-Code agent definition."""

    system_prompt: str
    user_prompt: str
