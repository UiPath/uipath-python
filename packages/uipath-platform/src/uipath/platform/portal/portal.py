"""Models for UiPath Portal service."""

from pydantic import BaseModel


class TenantInfo(BaseModel):
    """Model representing a tenant."""

    name: str
    id: str


class OrganizationInfo(BaseModel):
    """Model representing an organization."""

    id: str
    name: str


class TenantsAndOrganizationInfoResponse(BaseModel):
    """Model representing the tenants and organization info response."""

    tenants: list[TenantInfo]
    organization: OrganizationInfo
