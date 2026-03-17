from typing import TypedDict


class AuthConfig(TypedDict):
    """TypedDict for auth_config.json structure."""

    client_id: str
    port: int
    redirect_uri: str
    scope: str


class AccessTokenData(TypedDict):
    """TypedDict for access token data structure."""

    sub: str
    prt_id: str
    client_id: str
    exp: float
