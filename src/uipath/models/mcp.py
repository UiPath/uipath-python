from datetime import datetime
from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class McpServerType(IntEnum):
    UiPath = 0  # Processes, Agents, Activities
    Command = 1  # npx, uvx
    Coded = 2  # PackageType.McpServer
    SelfHosted = 3  # tunnel to (externally) self-hosted server
    Remote = 4  # HTTP connection to remote MCP server
    ProcessAssistant = 5  # Dynamic user process assistant


class McpServerStatus(IntEnum):
    Disconnected = 0
    Connected = 1


class McpServer(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    id: Optional[str] = Field(
        default=None,
        alias="id",
    )
    name: Optional[str] = Field(
        default=None,
        alias="name",
    )
    slug: Optional[str] = Field(
        default=None,
        alias="slug",
    )
    description: Optional[str] = Field(
        default=None,
        alias="description",
    )
    version: Optional[str] = Field(
        default=None,
        alias="version",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        alias="createdAt",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        alias="updatedAt",
    )
    is_active: Optional[bool] = Field(
        default=None,
        alias="isActive",
    )
    type: Optional[McpServerType] = Field(
        default=None,
        alias="type",
    )
    status: Optional[McpServerStatus] = Field(
        default=None,
        alias="status",
    )
    command: Optional[str] = Field(
        default=None,
        alias="command",
    )
    arguments: Optional[str] = Field(
        default=None,
        alias="arguments",
    )
    environment_variables: Optional[str] = Field(
        default=None,
        alias="environmentVariables",
    )
    process_key: Optional[str] = Field(default=None, alias="processKey")
    folder_key: Optional[str] = Field(
        default=None,
        alias="folderKey",
    )
    runtimes_count: Optional[int] = Field(
        default=None,
        alias="runtimesCount",
    )
    mcp_url: Optional[str] = Field(default=None, alias="mcpUrl")
