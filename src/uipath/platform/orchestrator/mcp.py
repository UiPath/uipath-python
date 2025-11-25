"""Models for MCP Servers in UiPath Orchestrator."""

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class McpServerType(IntEnum):
    """Enumeration of MCP server types."""

    UiPath = 0  # Processes, Agents, Activities
    Command = 1  # npx, uvx
    Coded = 2  # PackageType.McpServer
    SelfHosted = 3  # tunnel to (externally) self-hosted server
    Remote = 4  # HTTP connection to remote MCP server
    ProcessAssistant = 5  # Dynamic user process assistant


class McpServerStatus(IntEnum):
    """Enumeration of MCP server statuses."""

    Disconnected = 0
    Connected = 1


class McpServer(BaseModel):
    """Model representing an MCP server in UiPath Orchestrator."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    id: str | None = None
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    version: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_active: bool | None = None
    type: McpServerType | None = None
    status: McpServerStatus | None = None
    command: str | None = None
    arguments: str | None = None
    environment_variables: str | None = None
    process_key: str | None = None
    folder_key: str | None = None
    runtimes_count: int | None = None
    mcp_url: str | None = None
