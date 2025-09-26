"""Agent Models."""

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from uipath.models import Connection


class AgentResourceType(str, Enum):
    """Enum for resource types."""

    TOOL = "tool"
    CONTEXT = "context"
    ESCALATION = "escalation"


class BaseAgentResourceConfig(BaseModel):
    """Base resource model with common properties."""

    name: str
    description: str

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentUnknownResourceConfig(BaseAgentResourceConfig):
    """Fallback for unknown or future resource types."""

    resource_type: str = Field(alias="$resourceType")

    model_config = ConfigDict(extra="allow")


class BaseAgentToolResourceConfig(BaseAgentResourceConfig):
    """Tool resource with tool-specific properties."""

    resource_type: Literal[AgentResourceType.TOOL] = Field(alias="$resourceType")
    input_schema: Dict[str, Any] = Field(
        ..., alias="inputSchema", description="Input schema for the tool"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentToolType(str, Enum):
    """Agent tool type."""

    AGENT = "agent"
    INTEGRATION = "integration"


class AgentToolSettings(BaseModel):
    """Settings for tool configuration."""

    max_attempts: Optional[int] = Field(None, alias="maxAttempts")
    retry_delay: Optional[int] = Field(None, alias="retryDelay")
    timeout: Optional[int] = Field(None)

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentProcessToolProperties(BaseModel):
    """Properties specific to tool configuration."""

    folder_path: Optional[str] = Field(None, alias="folderPath")
    process_name: Optional[str] = Field(None, alias="processName")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentProcessToolResourceConfig(BaseAgentToolResourceConfig):
    """Tool resource with tool-specific properties."""

    type: Literal[AgentToolType.AGENT] = AgentToolType.AGENT
    output_schema: Dict[str, Any] = Field(
        ..., alias="outputSchema", description="Output schema for the tool"
    )
    properties: AgentProcessToolProperties = Field(
        ..., description="Tool-specific properties"
    )
    settings: AgentToolSettings = Field(
        default_factory=AgentToolSettings, description="Tool settings"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentIntegrationToolParameter(BaseModel):
    """Agent integration tool parameter."""

    name: str = Field(..., alias="name")
    type: str = Field(..., alias="type")
    value: Optional[Any] = Field(None, alias="value")
    field_location: str = Field(..., alias="fieldLocation")

    # Useful Metadata
    display_name: Optional[str] = Field(None, alias="displayName")
    display_value: Optional[str] = Field(None, alias="displayValue")
    description: Optional[str] = Field(None, alias="description")
    position: Optional[str] = Field(None, alias="position")
    field_variant: Optional[str] = Field(None, alias="fieldVariant")
    dynamic: Optional[bool] = Field(None, alias="dynamic")
    is_cascading: Optional[bool] = Field(None, alias="isCascading")
    sort_order: Optional[int] = Field(..., alias="sortOrder")
    required: Optional[bool] = Field(None, alias="required")
    # enum_values, dynamic_behavior and reference not typed currently

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentIntegrationToolProperties(BaseModel):
    """Properties specific to tool configuration."""

    tool_path: str = Field(..., alias="toolPath")
    object_name: str = Field(..., alias="objectName")
    tool_display_name: str = Field(..., alias="toolDisplayName")
    tool_description: str = Field(..., alias="toolDescription")
    method: str = Field(..., alias="method")
    connection: Connection = Field(..., alias="connection")
    body_structure: dict[str, Any] = Field(..., alias="bodyStructure")
    parameters: List[AgentIntegrationToolParameter] = Field([], alias="parameters")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentIntegrationToolResourceConfig(BaseAgentToolResourceConfig):
    """Tool resource with tool-specific properties."""

    type: Literal[AgentToolType.INTEGRATION] = AgentToolType.INTEGRATION
    properties: AgentIntegrationToolProperties
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentUnknownToolResourceConfig(BaseAgentToolResourceConfig):
    """Fallback for unknown or future tool types."""

    resource_type: Literal[AgentResourceType.TOOL] = AgentResourceType.TOOL
    type: str = Field(alias="$resourceType")

    model_config = ConfigDict(extra="allow")


class AgentContextSettings(BaseModel):
    """Settings for context configuration."""

    result_count: int = Field(alias="resultCount")
    retrieval_mode: Literal["Semantic", "Structured"] = Field(alias="retrievalMode")
    threshold: float = Field(default=0)

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentContextResourceConfig(BaseAgentResourceConfig):
    """Context resource with context-specific properties."""

    resource_type: Literal[AgentResourceType.CONTEXT] = Field(alias="$resourceType")
    folder_path: str = Field(alias="folderPath")
    index_name: str = Field(alias="indexName")
    settings: AgentContextSettings = Field(..., description="Context settings")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationRecipient(BaseModel):
    """Recipient for escalation."""

    type: int = Field(..., alias="type")
    value: str = Field(..., alias="value")
    display_name: Optional[str] = Field(default=None, alias="displayName")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationChannelProperties(BaseModel):
    """Agent escalation channel properties."""

    app_name: str = Field(..., alias="appName")
    app_version: int = Field(..., alias="appVersion")
    folder_name: Optional[str] = Field(..., alias="folderName")
    resource_key: str = Field(..., alias="resourceKey")
    is_actionable_message_enabled: Optional[bool] = Field(
        None, alias="isActionableMessageEnabled"
    )
    actionable_message_meta_data: Optional[Any] = Field(
        None, alias="actionableMessageMetaData"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationChannel(BaseModel):
    """Agent escalation channel."""

    id: str = Field(..., alias="id")
    name: str = Field(..., alias="name")
    type: str = Field(alias="type")
    description: str = Field(..., alias="description")
    input_schema: Dict[str, Any] = Field(
        ..., alias="inputSchema", description="Input schema for the escalation channel"
    )
    output_schema: Dict[str, Any] = Field(
        ...,
        alias="outputSchema",
        description="Output schema for the escalation channel",
    )
    properties: AgentEscalationChannelProperties = Field(..., alias="properties")
    recipients: List[AgentEscalationRecipient] = Field(..., alias="recipients")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationResourceConfig(BaseAgentResourceConfig):
    """Escalation resource with escalation-specific properties."""

    resource_type: Literal[AgentResourceType.ESCALATION] = Field(alias="$resourceType")
    channels: List[AgentEscalationChannel] = Field(alias="channels")

    # escalation_type: int = Field(..., alias="escalationType")
    is_agent_memory_enabled: bool = Field(alias="isAgentMemoryEnabled")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def custom_discriminator(data: Any) -> str:
    """Discriminator for resource types. This is required due to multi-key discrimination requirements for resources."""
    if isinstance(data, dict):
        resource_type = data.get("$resourceType")
        if resource_type == AgentResourceType.CONTEXT:
            return "AgentContextResourceConfig"
        elif resource_type == AgentResourceType.ESCALATION:
            return "AgentEscalationResourceConfig"
        elif resource_type == AgentResourceType.TOOL:
            tool_type = data.get("type")
            if tool_type == AgentToolType.AGENT:
                return "AgentProcessToolResourceConfig"
            elif tool_type == AgentToolType.INTEGRATION:
                return "AgentIntegrationToolResourceConfig"
            else:
                return "AgentUnknownToolResourceConfig"
        else:
            return "AgentUnknownResourceConfig"
    raise ValueError("Invalid discriminator values")


AgentResourceConfig = Annotated[
    Union[
        Annotated[
            AgentProcessToolResourceConfig, Tag("AgentProcessToolResourceConfig")
        ],
        Annotated[
            AgentIntegrationToolResourceConfig,
            Tag("AgentIntegrationToolResourceConfig"),
        ],
        Annotated[
            AgentUnknownToolResourceConfig, Tag("AgentUnknownToolResourceConfig")
        ],
        Annotated[AgentContextResourceConfig, Tag("AgentContextResourceConfig")],
        Annotated[AgentEscalationResourceConfig, Tag("AgentEscalationResourceConfig")],
        Annotated[AgentUnknownResourceConfig, Tag("AgentUnknownResourceConfig")],
    ],
    Field(discriminator=Discriminator(custom_discriminator)),
]


class BaseAgentDefinition(BaseModel):
    """Main agent model."""

    id: str = Field(..., description="Agent id or project name")
    name: str = Field(..., description="Agent name or project name")
    input_schema: Dict[str, Any] = Field(
        ..., alias="inputSchema", description="JSON schema for input arguments"
    )
    output_schema: Dict[str, Any] = Field(
        ..., alias="outputSchema", description="JSON schema for output arguments"
    )
    version: str = Field("1.0.0", description="Agent version")
    resources: List[AgentResourceConfig] = Field(
        ..., description="List of tools, context, and escalation resources"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentType(str, Enum):
    """Agent type."""

    LOW_CODE = "lowCode"


class AgentMessageRole(str, Enum):
    """Enum for message roles."""

    SYSTEM = "system"
    USER = "user"


class AgentMessage(BaseModel):
    """Message model for agent conversations."""

    role: AgentMessageRole
    content: str

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentSettings(BaseModel):
    """Settings for agent configuration."""

    engine: str = Field(..., description="Engine type, e.g., 'basic-v1'")
    model: str = Field(..., description="LLM model identifier")
    max_tokens: int = Field(
        ..., alias="maxTokens", description="Maximum number of tokens"
    )
    temperature: float = Field(..., description="Temperature for response generation")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class LowCodeAgentDefinition(BaseAgentDefinition):
    """Low code agent definition."""

    type: Literal[AgentType.LOW_CODE] = AgentType.LOW_CODE
    messages: List[AgentMessage] = Field(
        ..., description="List of system and user messages"
    )
    features: List[Any] = Field(
        default_factory=list, description="Currently empty feature list"
    )
    settings: AgentSettings = Field(..., description="Agent settings configuration")


KnownAgentDefinition = Annotated[
    Union[LowCodeAgentDefinition,],
    Field(discriminator="type"),
]


class UnknownAgentDefinition(BaseAgentDefinition):
    """Fallback for unknown agent definitions."""

    type: str

    model_config = ConfigDict(extra="allow")


AgentDefinition = Union[KnownAgentDefinition, UnknownAgentDefinition]
