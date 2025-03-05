from typing import Any

from pydantic import BaseModel


class Connection(BaseModel):
    id: str
    name: str
    owner: str
    createTime: str
    updateTime: str
    state: str
    apiBaseUri: str
    elementInstanceId: int
    connector: Any
    isDefault: bool
    lastUsedTime: str
    connectionIdentity: str
    pollingIntervalInMinutes: int
    folder: Any
    elementVersion: str


class ConnectionToken(BaseModel):
    accessToken: str
    tokenType: str
    scope: str
    expiresIn: int
    apiBaseUri: str
    elementInstanceId: int
