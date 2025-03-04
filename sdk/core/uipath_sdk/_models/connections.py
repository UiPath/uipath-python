from typing import TypedDict


class ConnectionPing(TypedDict):
    dateTime: str
    elementId: str
    hasTokenRefresh: str
    accessToken: str
    responseCode: str
    valid: bool
    accessTokenExpiry: str
    endpoint: str
    accessTokenScope: str
    instanceId: str
    authenticationType: str
    responseMessage: str
    connectionIdentity: str
