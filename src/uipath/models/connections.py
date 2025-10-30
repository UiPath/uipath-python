from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConnectionMetadata(BaseModel):
    """Metadata about a connection."""

    fields: dict[str, Any] = Field(default_factory=dict, alias="fields")
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Connection(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    id: Optional[str] = None
    name: Optional[str] = None
    owner: Optional[str] = None
    create_time: Optional[str] = Field(default=None, alias="createTime")
    update_time: Optional[str] = Field(default=None, alias="updateTime")
    state: Optional[str] = None
    api_base_uri: Optional[str] = Field(default=None, alias="apiBaseUri")
    element_instance_id: int = Field(alias="elementInstanceId")
    connector: Optional[Any] = None
    is_default: Optional[bool] = Field(default=None, alias="isDefault")
    last_used_time: Optional[str] = Field(default=None, alias="lastUsedTime")
    connection_identity: Optional[str] = Field(default=None, alias="connectionIdentity")
    polling_interval_in_minutes: Optional[int] = Field(
        default=None, alias="pollingIntervalInMinutes"
    )
    folder: Optional[Any] = None
    element_version: Optional[str] = Field(default=None, alias="elementVersion")


class ConnectionTokenType(str, Enum):
    DIRECT = "direct"
    BEARER = "bearer"


class ConnectionToken(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    access_token: str = Field(alias="accessToken")
    token_type: Optional[str] = Field(default=None, alias="tokenType")
    scope: Optional[str] = None
    expires_in: Optional[int] = Field(default=None, alias="expiresIn")
    api_base_uri: Optional[str] = Field(default=None, alias="apiBaseUri")
    element_instance_id: Optional[int] = Field(default=None, alias="elementInstanceId")


class EventArguments(BaseModel):
    event_connector: Optional[str] = Field(default=None, alias="UiPathEventConnector")
    event: Optional[str] = Field(default=None, alias="UiPathEvent")
    event_object_type: Optional[str] = Field(
        default=None, alias="UiPathEventObjectType"
    )
    event_object_id: Optional[str] = Field(default=None, alias="UiPathEventObjectId")
    additional_event_data: Optional[str] = Field(
        default=None, alias="UiPathAdditionalEventData"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )
