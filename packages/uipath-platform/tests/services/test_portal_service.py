import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath.platform.portal import (
    PortalService,
    TenantsAndOrganizationInfoResponse,
)

SAMPLE_RESPONSE = {
    "tenants": [
        {"name": "TenantA", "id": "tenant-id-1"},
        {"name": "TenantB", "id": "tenant-id-2"},
    ],
    "organization": {"id": "org-id-1", "name": "MyOrg"},
}


class TestPortalServiceGetTenantsAndOrganizations:
    def test_success(self, httpx_mock: HTTPXMock):
        domain = "https://cloud.uipath.com"
        prt_id = "my-org"
        access_token = "my-access-token"
        url = f"{domain}/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"

        httpx_mock.add_response(
            url=url,
            method="GET",
            status_code=200,
            json=SAMPLE_RESPONSE,
        )

        result = PortalService.get_tenants_and_organizations(
            domain=domain,
            prt_id=prt_id,
            access_token=access_token,
        )

        assert isinstance(result, TenantsAndOrganizationInfoResponse)
        assert len(result.tenants) == 2
        assert result.tenants[0].name == "TenantA"
        assert result.organization.name == "MyOrg"

    def test_401_raises(self, httpx_mock: HTTPXMock):
        domain = "https://cloud.uipath.com"
        prt_id = "my-org"
        url = f"{domain}/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"

        httpx_mock.add_response(
            url=url,
            method="GET",
            status_code=401,
            json={"error": "Unauthorized"},
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            PortalService.get_tenants_and_organizations(
                domain=domain,
                prt_id=prt_id,
                access_token="bad-token",
            )

        assert exc_info.value.response.status_code == 401

    def test_sends_bearer_token(self, httpx_mock: HTTPXMock):
        domain = "https://cloud.uipath.com"
        prt_id = "my-org"
        access_token = "secret-bearer-token"
        url = f"{domain}/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"

        httpx_mock.add_response(
            url=url,
            method="GET",
            status_code=200,
            json=SAMPLE_RESPONSE,
        )

        PortalService.get_tenants_and_organizations(
            domain=domain,
            prt_id=prt_id,
            access_token=access_token,
        )

        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert requests[0].headers["Authorization"] == f"Bearer {access_token}"
