"""Portal service for UiPath Platform."""

import httpx

from ..common._http_config import get_httpx_client_kwargs
from .portal import TenantsAndOrganizationInfoResponse


class PortalService:
    """Service for interacting with the UiPath Portal API.

    This service does not extend BaseService because it may be used before a full
    execution context is established — e.g., to resolve the current tenant and
    organization based on a user token, which is a prerequisite for building the
    base URL that other services depend on.

    The access_token is passed per call rather than stored on the instance because
    it may change over its lifetime (e.g., after a token refresh).
    """

    def __init__(self, domain: str):
        """Initialize the PortalService.

        Args:
            domain: The base URL of the UiPath platform (e.g., "https://cloud.uipath.com").
        """
        self._domain = domain

    def get_tenants_and_organizations(
        self,
        prt_id: str,
        access_token: str,
    ) -> TenantsAndOrganizationInfoResponse:
        """Retrieve tenants and organization info for the given organization.

        Args:
            prt_id: The organization/partition ID used in the URL path.
            access_token: The Bearer access token for authorization.

        Returns:
            TenantsAndOrganizationInfoResponse containing tenants and organization info.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        url = f"{self._domain}/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        with httpx.Client(**get_httpx_client_kwargs()) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return TenantsAndOrganizationInfoResponse.model_validate(response.json())

    async def get_tenants_and_organizations_async(
        self,
        prt_id: str,
        access_token: str,
    ) -> TenantsAndOrganizationInfoResponse:
        """Retrieve tenants and organization info for the given organization.

        Args:
            prt_id: The organization/partition ID used in the URL path.
            access_token: The Bearer access token for authorization.

        Returns:
            TenantsAndOrganizationInfoResponse containing tenants and organization info.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        url = f"{self._domain}/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return TenantsAndOrganizationInfoResponse.model_validate(response.json())
