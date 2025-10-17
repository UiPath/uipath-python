"""Agent Models."""

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, field_validator

from uipath.models import Connection


class AgentResourceType(str, Enum):
    """Enum for resource types."""

    TOOL = "tool"
    CONTEXT = "context"
    ESCALATION = "escalation"
    MCP = "mcp"


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
    PROCESS = "process"
    API = "api"
    PROCESS_ORCHESTRATION = "processorchestration"
    INTEGRATION = "integration"


class AgentToolSettings(BaseModel):
    """Settings for tool."""

    max_attempts: Optional[int] = Field(None, alias="maxAttempts")
    retry_delay: Optional[int] = Field(None, alias="retryDelay")
    timeout: Optional[int] = Field(None)

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class BaseResourceProperties(BaseModel):
    """Base resource properties."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentProcessToolProperties(BaseResourceProperties):
    """Properties specific to tool configuration."""

    folder_path: Optional[str] = Field(None, alias="folderPath")
    process_name: Optional[str] = Field(None, alias="processName")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentProcessToolResourceConfig(BaseAgentToolResourceConfig):
    """Tool resource with tool-specific properties."""

    type: Literal[
        AgentToolType.AGENT,
        AgentToolType.PROCESS,
        AgentToolType.API,
        AgentToolType.PROCESS_ORCHESTRATION,
    ]
    output_schema: Dict[str, Any] = Field(
        ..., alias="outputSchema", description="Output schema for the tool"
    )
    properties: AgentProcessToolProperties = Field(
        ..., description="Tool-specific properties"
    )
    settings: AgentToolSettings = Field(
        default_factory=AgentToolSettings, description="Tool settings"
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> str:
        """Normalize tool type to lowercase format."""
        if isinstance(v, str):
            return v.lower()
        return v

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


class AgentIntegrationToolProperties(BaseResourceProperties):
    """Properties specific to tool."""

    tool_path: str = Field(..., alias="toolPath")
    object_name: str = Field(..., alias="objectName")
    tool_display_name: str = Field(..., alias="toolDisplayName")
    tool_description: str = Field(..., alias="toolDescription")
    method: str = Field(..., alias="method")
    connection: Connection = Field(..., alias="connection")
    body_structure: Optional[dict[str, Any]] = Field(None, alias="bodyStructure")
    parameters: List[AgentIntegrationToolParameter] = Field([], alias="parameters")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentIntegrationToolResourceConfig(BaseAgentToolResourceConfig):
    """Tool resource with tool-specific properties."""

    type: Literal[AgentToolType.INTEGRATION] = AgentToolType.INTEGRATION
    properties: AgentIntegrationToolProperties
    arguments: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Tool arguments"
    )
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> str:
        """Normalize tool type to lowercase format."""
        if isinstance(v, str):
            return v.lower()
        return v

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentUnknownToolResourceConfig(BaseAgentResourceConfig):
    """Fallback for unknown or future tool types."""

    resource_type: Literal[AgentResourceType.TOOL] = AgentResourceType.TOOL
    type: str = Field(alias="$resourceType")
    arguments: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Tool arguments"
    )
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")

    model_config = ConfigDict(extra="allow")


class AgentContextQuerySetting(BaseModel):
    """Query setting for context configuration."""

    description: Optional[str] = Field(None)
    variant: Optional[str] = Field(None)

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentContextValueSetting(BaseModel):
    """Generic value setting for context configuration."""

    value: Any = Field(...)

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentContextOutputColumn(BaseModel):
    """Output column configuration for Batch Transform."""

    name: str = Field(...)
    description: Optional[str] = Field(None)

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentContextSettings(BaseModel):
    """Settings for context."""

    result_count: int = Field(alias="resultCount")
    retrieval_mode: Literal["Semantic", "Structured", "DeepRAG", "BatchTransform"] = (
        Field(alias="retrievalMode")
    )
    threshold: float = Field(default=0)
    query: Optional[AgentContextQuerySetting] = Field(None)
    folder_path_prefix: Optional[Union[Dict[str, Any], AgentContextValueSetting]] = (
        Field(None, alias="folderPathPrefix")
    )
    file_extension: Optional[Union[Dict[str, Any], AgentContextValueSetting]] = Field(
        None, alias="fileExtension"
    )
    citation_mode: Optional[AgentContextValueSetting] = Field(
        None, alias="citationMode"
    )
    web_search_grounding: Optional[AgentContextValueSetting] = Field(
        None, alias="webSearchGrounding"
    )
    output_columns: Optional[List[AgentContextOutputColumn]] = Field(
        None, alias="outputColumns"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentContextResourceConfig(BaseAgentResourceConfig):
    """Context resource with context-specific properties."""

    resource_type: Literal[AgentResourceType.CONTEXT] = Field(alias="$resourceType")
    folder_path: str = Field(alias="folderPath")
    index_name: str = Field(alias="indexName")
    settings: AgentContextSettings = Field(..., description="Context settings")
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentMcpTool(BaseModel):
    """MCP available tool."""

    name: str = Field(..., alias="name")
    description: str = Field(..., alias="description")
    input_schema: Dict[str, Any] = Field(..., alias="inputSchema")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentMcpResourceConfig(BaseAgentResourceConfig):
    """MCP resource configuration."""

    resource_type: Literal[AgentResourceType.MCP] = Field(alias="$resourceType")
    folder_path: str = Field(alias="folderPath")
    slug: str = Field(..., alias="slug")
    available_tools: List[AgentMcpTool] = Field(..., alias="availableTools")
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationRecipientType(str, Enum):
    """Enum for escalation recipient types."""

    USER_ID = "UserId"
    GROUP_ID = "GroupId"
    USER_EMAIL = "UserEmail"


class AgentEscalationRecipient(BaseModel):
    """Recipient for escalation."""

    type: Union[AgentEscalationRecipientType, str] = Field(..., alias="type")
    value: str = Field(..., alias="value")
    display_name: Optional[str] = Field(default=None, alias="displayName")

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> str:
        """Normalize recipient type from int (1=UserId, 2=GroupId, 3=UserEmail) or string. Unknown integers are converted to string."""
        if isinstance(v, int):
            mapping = {
                1: AgentEscalationRecipientType.USER_ID,
                2: AgentEscalationRecipientType.GROUP_ID,
                3: AgentEscalationRecipientType.USER_EMAIL,
            }
            return mapping.get(v, str(v))
        return v

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationChannelProperties(BaseResourceProperties):
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

    id: Optional[str] = Field(None, alias="id")
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
    outcome_mapping: Optional[Dict[str, str]] = Field(None, alias="outcomeMapping")
    properties: AgentEscalationChannelProperties = Field(..., alias="properties")
    recipients: List[AgentEscalationRecipient] = Field(..., alias="recipients")
    task_title: Optional[str] = Field(default=None, alias="taskTitle")
    priority: Optional[str] = None
    labels: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationResourceConfig(BaseAgentResourceConfig):
    """Escalation resource with escalation-specific properties."""

    id: Optional[str] = Field(None, alias="id")
    resource_type: Literal[AgentResourceType.ESCALATION] = Field(alias="$resourceType")
    channels: List[AgentEscalationChannel] = Field(alias="channels")
    is_agent_memory_enabled: bool = Field(default=False, alias="isAgentMemoryEnabled")
    escalation_type: int = Field(default=0, alias="escalationType")

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
        elif resource_type == AgentResourceType.MCP:
            return "AgentMcpResourceConfig"
        elif resource_type == AgentResourceType.TOOL:
            tool_type = data.get("type")
            if tool_type in [
                AgentToolType.AGENT,
                AgentToolType.PROCESS,
                AgentToolType.API,
                AgentToolType.PROCESS_ORCHESTRATION,
            ]:
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
        Annotated[AgentMcpResourceConfig, Tag("AgentMcpResourceConfig")],
        Annotated[AgentUnknownResourceConfig, Tag("AgentUnknownResourceConfig")],
    ],
    Field(discriminator=Discriminator(custom_discriminator)),
]


class AgentMetadata(BaseModel):
    """Metadata for agent."""

    is_conversational: bool = Field(alias="isConversational")
    storage_version: str = Field(alias="storageVersion")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentMessageRole(str, Enum):
    """Enum for message roles."""

    SYSTEM = "system"
    USER = "user"


class AgentMessage(BaseModel):
    """Message model for agent definition."""

    role: Literal[AgentMessageRole.SYSTEM, AgentMessageRole.USER]
    content: str

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Any) -> str:
        """Normalize role to lowercase format."""
        if isinstance(v, str):
            return v.lower()
        return v

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentSettings(BaseModel):
    """Settings for agent."""

    engine: str = Field(..., description="Engine type, e.g., 'basic-v1'")
    model: str = Field(..., description="LLM model")
    max_tokens: int = Field(
        ..., alias="maxTokens", description="Maximum number of tokens per completion"
    )
    temperature: float = Field(..., description="Temperature for response generation")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class BaseAgentDefinition(BaseModel):
    """Agent definition model."""

    input_schema: Dict[str, Any] = Field(
        ..., alias="inputSchema", description="JSON schema for input arguments"
    )
    output_schema: Dict[str, Any] = Field(
        ..., alias="outputSchema", description="JSON schema for output arguments"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentType(str, Enum):
    """Agent type."""

    LOW_CODE = "lowCode"
    CODED = "coded"


class LowCodeAgentDefinition(BaseAgentDefinition):
    """Low code agent definition."""

    type: Literal[AgentType.LOW_CODE] = AgentType.LOW_CODE

    id: str = Field(..., description="Agent id or project name")
    name: str = Field(..., description="Agent name or project name")
    metadata: Optional[AgentMetadata] = Field(None, description="Agent metadata")
    messages: List[AgentMessage] = Field(
        ..., description="List of system and user messages"
    )

    version: str = Field("1.0.0", description="Agent version")
    resources: List[AgentResourceConfig] = Field(
        ..., description="List of tools, context, mcp and escalation resources"
    )
    features: List[Any] = Field(default_factory=list, description="Agent feature list")
    settings: AgentSettings = Field(..., description="Agent settings")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class CodedAgentDefinition(BaseAgentDefinition):
    """Coded agent definition."""

    type: Literal[AgentType.CODED] = AgentType.CODED

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


KnownAgentDefinition = Annotated[
    Union[LowCodeAgentDefinition,],
    Field(discriminator="type"),
]


class UnknownAgentDefinition(BaseAgentDefinition):
    """Fallback for unknown agent definitions."""

    type: str

    model_config = ConfigDict(extra="allow")


AgentDefinition = Union[KnownAgentDefinition, UnknownAgentDefinition]
