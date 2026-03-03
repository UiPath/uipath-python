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


class TenantInfo(TypedDict):
    """TypedDict for tenant info structure."""

    name: str
    id: str


class OrganizationInfo(TypedDict):
    """TypedDict for organization info structure."""

    id: str
    name: str


class TenantsAndOrganizationInfoResponse(TypedDict):
    """TypedDict for tenants and organization info response structure."""

    tenants: list[TenantInfo]
    organization: OrganizationInfo
