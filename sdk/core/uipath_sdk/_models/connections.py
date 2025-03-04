from typing import Optional

from pydantic import BaseModel


class ConnectionPing(BaseModel):
    dateTime: Optional[str] = None
    elementId: Optional[str] = None
    hasTokenRefresh: Optional[bool] = None
    accessToken: Optional[str] = None
    responseCode: Optional[str] = None
    valid: Optional[bool] = None
    accessTokenExpiry: Optional[str] = None
    endpoint: Optional[str] = None
    accessTokenScope: Optional[str] = None
    instanceId: Optional[str] = None
    authenticationType: Optional[str] = None
    responseMessage: Optional[str] = None
    connectionIdentity: Optional[str] = None
