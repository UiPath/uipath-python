from typing import TypedDict

from pydantic import BaseModel


class AuthConfig(BaseModel):
    """OIDC auth configuration."""

    client_id: str
    scope: str


class AuthorizationRequest(BaseModel):
    """Result of building an OAuth2 PKCE authorization URL."""

    url: str
    code_verifier: str
    state: str


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
