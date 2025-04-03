from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Connection(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
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


class ConnectionToken(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )

    access_token: str = Field(alias="accessToken")
    token_type: Optional[str] = Field(default=None, alias="tokenType")
    scope: Optional[str] = None
    expires_in: Optional[int] = Field(default=None, alias="expiresIn")
    api_base_uri: Optional[str] = Field(default=None, alias="apiBaseUri")
    element_instance_id: Optional[int] = Field(default=None, alias="elementInstanceId")
