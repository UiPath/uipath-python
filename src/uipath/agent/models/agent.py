"""Agent Models."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from uipath.models import Connection
from uipath.models.guardrails import (
    BuiltInValidatorGuardrail,
    CustomGuardrail,
    FieldReference,
)


class AgentResourceType(str, Enum):
    """Agent resource type enumeration."""

    TOOL = "tool"
    CONTEXT = "context"
    ESCALATION = "escalation"
    MCP = "mcp"
    UNKNOWN = "unknown"  # fallback branch discriminator


class AgentToolType(str, Enum):
    """Agent tool type enumeration."""

    AGENT = "Agent"
    PROCESS = "Process"
    API = "Api"
    PROCESS_ORCHESTRATION = "ProcessOrchestration"
    INTEGRATION = "Integration"
    UNKNOWN = "Unknown"  # fallback branch discriminator


class AgentEscalationRecipientType(str, Enum):
    """Agent escalation recipient type enumeration."""

    USER_ID = "UserId"
    GROUP_ID = "GroupId"
    USER_EMAIL = "UserEmail"


class AgentContextRetrievalMode(str, Enum):
    """Agent context retrieval mode enumeration."""

    SEMANTIC = "Semantic"
    STRUCTURED = "Structured"
    DEEP_RAG = "DeepRAG"
    BATCH_TRANSFORM = "BatchTransform"
    UNKNOWN = "Unknown"  # fallback branch discriminator


class AgentMessageRole(str, Enum):
    """Agent message role enumeration."""

    SYSTEM = "system"
    USER = "user"


class AgentGuardrailActionType(str, Enum):
    """Agent guardrail action type enumeration."""

    BLOCK = "block"
    ESCALATE = "escalate"
    FILTER = "filter"
    LOG = "log"
    UNKNOWN = "unknown"  # fallback branch discriminator


class BaseCfg(BaseModel):
    """Base configuration model with common settings."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class BaseResourceProperties(BaseCfg):
    """Base resource properties model."""

    pass


class AgentToolSettings(BaseCfg):
    """Agent tool settings model."""

    max_attempts: Optional[int] = Field(None, alias="maxAttempts")
    retry_delay: Optional[int] = Field(None, alias="retryDelay")
    timeout: Optional[int] = Field(None)


class BaseAgentResourceConfig(BaseCfg):
    """Base agent resource configuration model."""

    name: str
    description: str
    # NOTE: this is the union discriminator; don't attach validators here.
    resource_type: Literal[
        AgentResourceType.TOOL,
        AgentResourceType.CONTEXT,
        AgentResourceType.ESCALATION,
        AgentResourceType.MCP,
        AgentResourceType.UNKNOWN,
    ] = Field(alias="$resourceType")


class AgentUnknownResourceConfig(BaseAgentResourceConfig):
    """Fallback for unknown or future resource types."""

    resource_type: Literal[AgentResourceType.UNKNOWN] = Field(
        alias="$resourceType", default=AgentResourceType.UNKNOWN, frozen=True
    )


class AgentContextQuerySetting(BaseCfg):
    """Agent context query setting model."""

    description: Optional[str] = Field(None)
    variant: Optional[str] = Field(None)


class AgentContextValueSetting(BaseCfg):
    """Agent context value setting model."""

    value: Any = Field(...)


class AgentContextOutputColumn(BaseCfg):
    """Agent context output column model."""

    name: str = Field(...)
    description: Optional[str] = Field(None)


class AgentContextSettings(BaseCfg):
    """Agent context settings model."""

    result_count: int = Field(alias="resultCount")
    # Allow Unknown explicitly so we can serialize deterministically
    retrieval_mode: Literal[
        AgentContextRetrievalMode.SEMANTIC,
        AgentContextRetrievalMode.STRUCTURED,
        AgentContextRetrievalMode.DEEP_RAG,
        AgentContextRetrievalMode.BATCH_TRANSFORM,
        AgentContextRetrievalMode.UNKNOWN,
    ] = Field(alias="retrievalMode")
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


class AgentContextResourceConfig(BaseAgentResourceConfig):
    """Agent context resource configuration model."""

    resource_type: Literal[AgentResourceType.CONTEXT] = Field(
        alias="$resourceType", default=AgentResourceType.CONTEXT, frozen=True
    )
    folder_path: str = Field(alias="folderPath")
    index_name: str = Field(alias="indexName")
    settings: AgentContextSettings = Field(..., description="Context settings")
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")


class AgentMcpTool(BaseCfg):
    """Agent MCP tool model."""

    name: str = Field(..., alias="name")
    description: str = Field(..., alias="description")
    input_schema: Dict[str, Any] = Field(..., alias="inputSchema")


class AgentMcpResourceConfig(BaseAgentResourceConfig):
    """Agent MCP resource configuration model."""

    resource_type: Literal[AgentResourceType.MCP] = Field(
        alias="$resourceType", default=AgentResourceType.MCP, frozen=True
    )
    folder_path: str = Field(alias="folderPath")
    slug: str = Field(..., alias="slug")
    available_tools: List[AgentMcpTool] = Field(..., alias="availableTools")
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")


class AgentEscalationRecipient(BaseCfg):
    """Agent escalation recipient model."""

    type: Union[AgentEscalationRecipientType, str] = Field(..., alias="type")
    value: str = Field(..., alias="value")
    display_name: Optional[str] = Field(default=None, alias="displayName")

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> Any:
        """Normalize recipient type from int to enum/string."""
        if isinstance(v, int):
            mapping = {
                1: AgentEscalationRecipientType.USER_ID,
                2: AgentEscalationRecipientType.GROUP_ID,
                3: AgentEscalationRecipientType.USER_EMAIL,
            }
            return mapping.get(v, str(v))
        return v


class AgentEscalationChannelProperties(BaseResourceProperties):
    """Agent escalation channel properties model."""

    app_name: str = Field(..., alias="appName")
    app_version: int = Field(..., alias="appVersion")
    folder_name: Optional[str] = Field(None, alias="folderName")
    resource_key: str = Field(..., alias="resourceKey")
    is_actionable_message_enabled: Optional[bool] = Field(
        None, alias="isActionableMessageEnabled"
    )
    actionable_message_meta_data: Optional[Any] = Field(
        None, alias="actionableMessageMetaData"
    )


class AgentEscalationChannel(BaseCfg):
    """Agent escalation channel model."""

    id: Optional[str] = Field(None, alias="id")
    name: str = Field(..., alias="name")
    type: str = Field(alias="type")
    description: str = Field(..., alias="description")
    input_schema: Dict[str, Any] = Field(..., alias="inputSchema")
    output_schema: Dict[str, Any] = Field(..., alias="outputSchema")
    outcome_mapping: Optional[Dict[str, str]] = Field(None, alias="outcomeMapping")
    properties: AgentEscalationChannelProperties = Field(..., alias="properties")
    recipients: List[AgentEscalationRecipient] = Field(..., alias="recipients")
    task_title: Optional[str] = Field(default=None, alias="taskTitle")
    priority: Optional[str] = None
    labels: List[str] = Field(default_factory=list)


class AgentEscalationResourceConfig(BaseAgentResourceConfig):
    """Agent escalation resource configuration model."""

    id: Optional[str] = Field(None, alias="id")
    resource_type: Literal[AgentResourceType.ESCALATION] = Field(
        alias="$resourceType", default=AgentResourceType.ESCALATION, frozen=True
    )
    channels: List[AgentEscalationChannel] = Field(alias="channels")
    is_agent_memory_enabled: bool = Field(default=False, alias="isAgentMemoryEnabled")
    escalation_type: int = Field(default=0, alias="escalationType")


class BaseAgentToolResourceConfig(BaseAgentResourceConfig):
    """Base agent tool resource configuration model."""

    resource_type: Literal[AgentResourceType.TOOL] = Field(
        alias="$resourceType", default=AgentResourceType.TOOL, frozen=True
    )
    input_schema: Dict[str, Any] = Field(..., alias="inputSchema")


class AgentProcessToolProperties(BaseResourceProperties):
    """Agent process tool properties model."""

    folder_path: Optional[str] = Field(None, alias="folderPath")
    process_name: Optional[str] = Field(None, alias="processName")


class AgentProcessToolResourceConfig(BaseAgentToolResourceConfig):
    """Agent process tool resource configuration model."""

    type: Literal[
        AgentToolType.AGENT,
        AgentToolType.PROCESS,
        AgentToolType.API,
        AgentToolType.PROCESS_ORCHESTRATION,
    ]
    output_schema: Dict[str, Any] = Field(..., alias="outputSchema")
    properties: AgentProcessToolProperties
    settings: AgentToolSettings = Field(default_factory=AgentToolSettings)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class AgentIntegrationToolParameter(BaseCfg):
    """Agent integration tool parameter model."""

    name: str = Field(..., alias="name")
    type: str = Field(..., alias="type")
    value: Optional[Any] = Field(None, alias="value")
    field_location: str = Field(..., alias="fieldLocation")

    # Optional metadata
    display_name: Optional[str] = Field(None, alias="displayName")
    display_value: Optional[str] = Field(None, alias="displayValue")
    description: Optional[str] = Field(None, alias="description")
    position: Optional[str] = Field(None, alias="position")
    field_variant: Optional[str] = Field(None, alias="fieldVariant")
    dynamic: Optional[bool] = Field(None, alias="dynamic")
    is_cascading: Optional[bool] = Field(None, alias="isCascading")
    sort_order: Optional[int] = Field(None, alias="sortOrder")
    required: Optional[bool] = Field(None, alias="required")


class AgentIntegrationToolProperties(BaseResourceProperties):
    """Agent integration tool properties model."""

    tool_path: str = Field(..., alias="toolPath")
    object_name: str = Field(..., alias="objectName")
    tool_display_name: str = Field(..., alias="toolDisplayName")
    tool_description: str = Field(..., alias="toolDescription")
    method: str = Field(..., alias="method")
    connection: Connection = Field(..., alias="connection")
    body_structure: Optional[dict[str, Any]] = Field(None, alias="bodyStructure")
    parameters: List[AgentIntegrationToolParameter] = Field(
        default_factory=list, alias="parameters"
    )


class AgentIntegrationToolResourceConfig(BaseAgentToolResourceConfig):
    """Agent integration tool resource configuration model."""

    type: Literal[AgentToolType.INTEGRATION] = AgentToolType.INTEGRATION
    properties: AgentIntegrationToolProperties
    settings: Optional[AgentToolSettings] = Field(None)
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")


class AgentUnknownToolResourceConfig(BaseAgentToolResourceConfig):
    """Fallback for unknown tool types (parent normalizer sets type='Unknown')."""

    type: Literal[AgentToolType.UNKNOWN] = AgentToolType.UNKNOWN
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_enabled: Optional[bool] = Field(None, alias="isEnabled")


ToolResourceConfig = Annotated[
    Union[
        AgentProcessToolResourceConfig,
        AgentIntegrationToolResourceConfig,
        AgentUnknownToolResourceConfig,  # when parent sets type="Unknown"
    ],
    Field(discriminator="type"),
]

AgentResourceConfig = Annotated[
    Union[
        ToolResourceConfig,  # nested discrim on 'type'
        AgentContextResourceConfig,
        AgentEscalationResourceConfig,
        AgentMcpResourceConfig,
        AgentUnknownResourceConfig,  # when parent sets resource_type="Unknown"
    ],
    Field(discriminator="resource_type"),
]


class AgentGuardrailBlockAction(BaseModel):
    """Agent guardrail block action model."""

    action_type: Literal[AgentGuardrailActionType.BLOCK] = Field(
        alias="$actionType", default=AgentGuardrailActionType.BLOCK, frozen=True
    )
    reason: str
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailFilterAction(BaseModel):
    """Agent guardrail filter action model."""

    action_type: Literal[AgentGuardrailActionType.FILTER] = Field(
        alias="$actionType", default=AgentGuardrailActionType.FILTER, frozen=True
    )
    fields: List[FieldReference]
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailSeverityLevel(str, Enum):
    """Severity level enumeration."""

    ERROR = "Error"
    INFO = "Info"
    WARNING = "Warning"


class AgentGuardrailLogAction(BaseModel):
    """Agent guardrail log action model."""

    action_type: Literal[AgentGuardrailActionType.LOG] = Field(
        alias="$actionType", default=AgentGuardrailActionType.LOG, frozen=True
    )
    message: Optional[str] = Field(None, alias="message")
    severity_level: AgentGuardrailSeverityLevel = Field(alias="severityLevel")
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailEscalateActionApp(BaseModel):
    """Agent guardrail escalate action app model."""

    id: Optional[str] = None
    version: int
    name: str
    folder_id: Optional[str] = Field(None, alias="folderId")
    folder_name: str = Field(alias="folderName")
    app_process_key: Optional[str] = Field(None, alias="appProcessKey")
    runtime: Optional[str] = None
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailEscalateAction(BaseModel):
    """Agent guardrail escalate action model."""

    action_type: Literal[AgentGuardrailActionType.ESCALATE] = Field(
        alias="$actionType", default=AgentGuardrailActionType.ESCALATE, frozen=True
    )
    app: AgentGuardrailEscalateActionApp
    recipient: "AgentEscalationRecipient"  # forward ref ok
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailUnknownAction(BaseModel):
    """Fallback for unknown guardrail actions."""

    action_type: Literal[AgentGuardrailActionType.UNKNOWN] = Field(
        alias="$actionType", default=AgentGuardrailActionType.UNKNOWN, frozen=True
    )
    # Accept arbitrary payload for forward-compat
    details: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(populate_by_name=True, extra="allow")


GuardrailAction = Annotated[
    Union[
        AgentGuardrailBlockAction,
        AgentGuardrailFilterAction,
        AgentGuardrailLogAction,
        AgentGuardrailEscalateAction,
        AgentGuardrailUnknownAction,  # when parent sets $actionType="unknown"
    ],
    Field(discriminator="action_type"),
]


class AgentBuiltInValidatorGuardrail(BuiltInValidatorGuardrail):
    """Agent built-in validator guardrail with action capabilities."""

    action: GuardrailAction = Field(
        ..., description="Action to take when guardrail is triggered"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentCustomGuardrail(CustomGuardrail):
    """Agent custom guardrail with action capabilities."""

    action: GuardrailAction = Field(
        ..., description="Action to take when guardrail is triggered"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentUnknownGuardrail(BaseCfg):
    """Fallback wrapper for unknown guardrail kinds."""

    guardrail_type: Literal["unknown"] = Field(
        alias="$guardrailType", default="unknown", frozen=True
    )
    # store the original payload under 'raw' for round-trip/debug
    raw: Dict[str, Any]


AgentGuardrail = Annotated[
    Union[
        # known kinds from SDK
        AgentCustomGuardrail,
        AgentBuiltInValidatorGuardrail,
        # unknown kind fallback
        AgentUnknownGuardrail,
    ],
    Field(discriminator="guardrail_type"),
]


class AgentMetadata(BaseCfg):
    """Agent metadata model."""

    is_conversational: bool = Field(alias="isConversational")
    storage_version: str = Field(alias="storageVersion")


class AgentMessage(BaseCfg):
    """Agent message model."""

    role: Literal[AgentMessageRole.SYSTEM, AgentMessageRole.USER]
    content: str

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Any) -> Any:
        """Normalize role to lowercase enum/string."""
        return v.lower() if isinstance(v, str) else v


class AgentSettings(BaseCfg):
    """Agent settings model."""

    engine: str
    model: str
    max_tokens: int = Field(..., alias="maxTokens")
    temperature: float


class AgentDefinition(BaseModel):
    """Unified agent definition with parent-level normalization for guardrails and resources."""

    input_schema: Dict[str, Any] = Field(..., alias="inputSchema")
    output_schema: Dict[str, Any] = Field(..., alias="outputSchema")
    guardrails: Optional[List[AgentGuardrail]] = Field(None)

    id: Optional[str] = None
    name: Optional[str] = None
    metadata: Optional[AgentMetadata] = None
    messages: List[AgentMessage]

    version: str = "1.0.0"
    resources: List[AgentResourceConfig]
    features: List[Any] = Field(default_factory=list)
    settings: AgentSettings

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    @staticmethod
    def _normalize_guardrails(v: Dict[str, Any]) -> None:
        guards = v.get("guardrails")
        if not isinstance(guards, list):
            return

        normalized = []
        for g in guards:
            if not isinstance(g, dict):
                normalized.append(g)
                continue

            gt = g.get("$guardrailType") or g.get("guardrail_type")
            # Normalize to the expected discriminator values
            if isinstance(gt, str):
                gt_lower = gt.lower()
                if gt_lower == "custom":
                    g["$guardrailType"] = "custom"
                elif gt_lower == "builtinvalidator":
                    g["$guardrailType"] = "builtInValidator"
                else:
                    # Unknown guardrail type
                    normalized.append({"guardrail_type": "unknown", "raw": g})
                    continue
            else:
                # Non-string guardrail type
                normalized.append({"guardrail_type": "unknown", "raw": g})
                continue

            # Normalize the action if present
            action = g.get("action")
            if isinstance(action, dict):
                at = action.get("$actionType")
                if isinstance(at, str):
                    at_lower = at.lower()
                    if at_lower in {"block", "filter", "log", "escalate"}:
                        # Valid action type, keep as-is or normalize case if needed
                        g["action"]["$actionType"] = at_lower
                    else:
                        # Unknown action type
                        g["action"] = {"$actionType": "unknown", "details": action}
                else:
                    # Non-string action type
                    g["action"] = {"$actionType": "unknown", "details": action}

            normalized.append(g)

        v["guardrails"] = normalized

    @staticmethod
    def _normalize_resources(v: Dict[str, Any]) -> None:
        KNOWN_RES = {"tool", "context", "escalation", "mcp"}
        TOOL_MAP = {
            "agent": "Agent",
            "process": "Process",
            "api": "Api",
            "processorchestration": "ProcessOrchestration",
            "integration": "Integration",
            "unknown": "Unknown",
        }
        CONTEXT_MODE_MAP = {
            "semantic": "Semantic",
            "structured": "Structured",
            "deeprag": "DeepRAG",
            "batchtransform": "BatchTransform",
            "unknown": "Unknown",
        }

        res_list = v.get("resources")
        if not isinstance(res_list, list):
            return

        out = []
        for res in res_list:
            if not isinstance(res, dict):
                out.append(res)
                continue

            rt = res.get("$resourceType") or res.get("resource_type")
            res["$resourceType"] = (
                rt.lower()
                if isinstance(rt, str) and rt.lower() in KNOWN_RES
                else "unknown"
            )

            if res["$resourceType"] == "tool":
                t = res.get("type")
                res["type"] = (
                    TOOL_MAP.get(t.lower(), "Unknown")
                    if isinstance(t, str)
                    else "Unknown"
                )

            if res["$resourceType"] == "context":
                settings = res.get("settings", {})
                rm = settings.get("retrievalMode") or settings.get("retrieval_mode")
                settings["retrievalMode"] = (
                    CONTEXT_MODE_MAP.get(rm.lower(), "Unknown")
                    if isinstance(rm, str)
                    else "Unknown"
                )
                res["settings"] = settings

            out.append(res)

        v["resources"] = out

    @model_validator(mode="before")
    @classmethod
    def _normalize_all(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        cls._normalize_guardrails(v)
        cls._normalize_resources(v)
        return v


LowCodeAgentDefinition = AgentDefinition
