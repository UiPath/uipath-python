from typing import Any, Optional

from pydantic import BaseModel


class Connection(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    owner: Optional[str] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None
    state: Optional[str] = None
    apiBaseUri: Optional[str] = None
    elementInstanceId: int
    connector: Optional[Any] = None
    isDefault: Optional[bool] = None
    lastUsedTime: Optional[str] = None
    connectionIdentity: Optional[str] = None
    pollingIntervalInMinutes: Optional[int] = None
    folder: Optional[Any] = None
    elementVersion: Optional[str] = None


class ConnectionToken(BaseModel):
    accessToken: str
    tokenType: Optional[str] = None
    scope: Optional[str] = None
    expiresIn: Optional[int] = None
    apiBaseUri: Optional[str] = None
    elementInstanceId: Optional[int] = None
