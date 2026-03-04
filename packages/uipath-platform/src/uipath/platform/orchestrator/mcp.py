"""Models for MCP Servers in UiPath Orchestrator."""

from datetime import datetime
from enum import IntEnum
from typing import Optional

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

    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    type: Optional[McpServerType] = None
    status: Optional[McpServerStatus] = None
    command: Optional[str] = None
    arguments: Optional[str] = None
    environment_variables: Optional[str] = None
    process_key: Optional[str] = None
    folder_key: Optional[str] = None
    runtimes_count: Optional[int] = None
    mcp_url: Optional[str] = None
