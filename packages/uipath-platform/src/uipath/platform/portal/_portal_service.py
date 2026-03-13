"""Portal service for UiPath Platform."""

import httpx

from ..common._http_config import get_httpx_client_kwargs
from .portal import TenantsAndOrganizationInfoResponse


class PortalService:
    """Service for interacting with the UiPath Portal API."""

    @staticmethod
    def get_tenants_and_organizations(
        domain: str,
        prt_id: str,
        access_token: str,
    ) -> TenantsAndOrganizationInfoResponse:
        """Retrieve tenants and organization info for the given organization.

        Args:
            domain: The base URL of the UiPath platform (e.g., "https://cloud.uipath.com").
            prt_id: The organization/partition ID used in the URL path.
            access_token: The Bearer access token for authorization.

        Returns:
            TenantsAndOrganizationInfoResponse containing tenants and organization info.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx response.
            httpx.ConnectError: If there is a network connectivity issue.
        """
        url = f"{domain}/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        with httpx.Client(**get_httpx_client_kwargs()) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return TenantsAndOrganizationInfoResponse.model_validate(response.json())
