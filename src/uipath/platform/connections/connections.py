"""Models for connections in the UiPath platform."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class ConnectionMetadata(BaseModel):
    """Metadata about a connection."""

    fields: dict[str, Any] = Field(default_factory=dict, alias="fields")
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

class Connection(BaseModel):
    """Model representing a connection in the UiPath platform."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    id: str | None = None
    name: str | None = None
    owner: str | None = None
    create_time: str | None = Field(default=None, alias="createTime")
    update_time: str | None = Field(default=None, alias="updateTime")
    state: str | None = None
    api_base_uri: str | None = Field(default=None, alias="apiBaseUri")
    element_instance_id: int = Field(alias="elementInstanceId")
    connector: Any | None = None
    is_default: bool | None = Field(default=None, alias="isDefault")
    last_used_time: str | None = Field(default=None, alias="lastUsedTime")
    connection_identity: str | None = Field(default=None, alias="connectionIdentity")
    polling_interval_in_minutes: int | None = Field(
        default=None, alias="pollingIntervalInMinutes"
    )
    folder: Any | None = None
    element_version: str | None = Field(default=None, alias="elementVersion")

class ConnectionTokenType(str, Enum):
    """Enum representing types of connection tokens."""

    DIRECT = "direct"
    BEARER = "bearer"

class ConnectionToken(BaseModel):
    """Model representing a connection token in the UiPath platform."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    access_token: str = Field(alias="accessToken")
    token_type: str | None = Field(default=None, alias="tokenType")
    scope: str | None = None
    expires_in: int | None = Field(default=None, alias="expiresIn")
    api_base_uri: str | None = Field(default=None, alias="apiBaseUri")
    element_instance_id: int | None = Field(default=None, alias="elementInstanceId")

class EventArguments(BaseModel):
    """Model representing event arguments for a connection."""

    event_connector: str | None = Field(default=None, alias="UiPathEventConnector")
    event: str | None = Field(default=None, alias="UiPathEvent")
    event_object_type: str | None = Field(
        default=None, alias="UiPathEventObjectType"
    )
    event_object_id: str | None = Field(default=None, alias="UiPathEventObjectId")
    additional_event_data: str | None = Field(
        default=None, alias="UiPathAdditionalEventData"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )

class ActivityParameterLocationInfo(BaseModel):
    """Information about parameter location in an activity."""

    query_params: list[str] = []
    header_params: list[str] = []
    path_params: list[str] = []
    multipart_params: list[str] = []
    body_fields: list[str] = []

class ActivityMetadata(BaseModel):
    """Metadata for an activity."""

    object_path: str
    method_name: str
    content_type: str
    parameter_location_info: ActivityParameterLocationInfo
