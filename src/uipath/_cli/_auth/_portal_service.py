import os
import time
from typing import Optional

import click
import httpx

from .._utils._console import ConsoleLogger
from ._models import TenantsAndOrganizationInfoResponse, TokenData
from ._oidc_utils import get_auth_config
from ._utils import (
    get_auth_data,
    get_parsed_token_data,
    update_auth_file,
    update_env_file,
)

console = ConsoleLogger()
client = httpx.Client(follow_redirects=True)


class PortalService:
    """Service for interacting with the UiPath Portal API."""

    access_token: Optional[str] = None
    prt_id: Optional[str] = None
    domain: Optional[str] = None
    selected_tenant: Optional[str] = None

    _tenants_and_organizations: Optional[TenantsAndOrganizationInfoResponse] = None

    def __init__(
        self,
        domain: str,
        access_token: Optional[str] = None,
        prt_id: Optional[str] = None,
    ):
        self.domain = domain
        self.access_token = access_token
        self.prt_id = prt_id

    def update_token_data(self, token_data: TokenData):
        self.access_token = token_data["access_token"]
        self.prt_id = get_parsed_token_data(token_data).get("prt_id")

    def get_tenants_and_organizations(self) -> TenantsAndOrganizationInfoResponse:
        url = f"https://{self.domain}.uipath.com/{self.prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"
        response = client.get(
            url, headers={"Authorization": f"Bearer {self.access_token}"}
        )
        if response.status_code < 400:
            result = response.json()
            self._tenants_and_organizations = result
            return result
        elif response.status_code == 401:
            console.error("Unauthorized")
        else:
            console.error(
                f"Failed to get tenants and organizations: {response.status_code} {response.text}"
            )
        # Can't reach here, console.error exits, linting
        raise Exception("Failed to get tenants")

    def get_uipath_orchestrator_url(self) -> str:
        if self._tenants_and_organizations is None:
            self._tenants_and_organizations = self.get_tenants_and_organizations()
        organization = self._tenants_and_organizations.get("organization")
        if organization is None:
            console.error("Organization not found.")
            return ""
        account_name = organization.get("name")
        return f"https://{self.domain}.uipath.com/{account_name}/{self.selected_tenant}/orchestrator_"

    def post_refresh_token_request(self, refresh_token: str) -> TokenData:
        url = f"https://{self.domain}.uipath.com/identity_/connect/token"
        client_id = get_auth_config().get("client_id")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = client.post(url, data=data, headers=headers)
        if response.status_code < 400:
            return response.json()
        elif response.status_code == 401:
            console.error("Unauthorized")
        else:
            console.error(f"Failed to refresh token: {response.status_code}")
        # Can't reach here, console.error exits, linting
        raise Exception("Failed to refresh get token")

    def ensure_valid_token(self):
        """Ensure the access token is valid and refresh it if necessary.

        This function should be called when running CLI commands to verify authentication.
        It checks if an auth file exists and contains a valid non-expired token.
        If the token is expired, it will attempt to refresh it.
        If no auth file exists, it will raise an exception.

        Raises:
            Exception: If no auth file exists or token refresh fails
        """
        auth_data = get_auth_data()
        claims = get_parsed_token_data(auth_data)
        exp = claims.get("exp")

        if exp is not None and float(exp) > time.time():
            if not os.getenv("UIPATH_URL"):
                tenants_and_organizations = self.get_tenants_and_organizations()
                select_tenant(
                    self.domain if self.domain else "alpha", tenants_and_organizations
                )
            return auth_data.get("access_token")

        refresh_token = auth_data.get("refresh_token")
        if refresh_token is None:
            raise Exception("Refresh token not found")
        token_data = self.post_refresh_token_request(refresh_token)
        update_auth_file(token_data)

        self.access_token = token_data["access_token"]
        self.prt_id = claims.get("prt_id")

        updated_env_contents = {
            "UIPATH_ACCESS_TOKEN": token_data["access_token"],
        }
        if not os.getenv("UIPATH_URL"):
            tenants_and_organizations = self.get_tenants_and_organizations()
            select_tenant(
                self.domain if self.domain else "alpha", tenants_and_organizations
            )

        update_env_file(updated_env_contents)

    def post_auth(self, base_url: str) -> None:
        or_base_url = (
            f"{base_url}/orchestrator_"
            if base_url
            else self.get_uipath_orchestrator_url()
        )

        url_try_enable_first_run = f"{or_base_url}/api/StudioWeb/TryEnableFirstRun"
        url_acquire_license = f"{or_base_url}/api/StudioWeb/AcquireLicense"

        try:
            [try_enable_first_run_response, acquire_license_response] = [
                client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
                for url in [url_try_enable_first_run, url_acquire_license]
            ]
        except Exception:
            pass

    def has_initialized_auth(self):
        try:
            auth_data = get_auth_data()
            if not auth_data or "access_token" not in auth_data:
                return False
            if not os.path.exists(".env"):
                return False
            if not os.getenv("UIPATH_ACCESS_TOKEN"):
                return False

            return True
        except Exception:
            return False


def select_tenant(
    domain: str, tenants_and_organizations: TenantsAndOrganizationInfoResponse
):
    tenant_names = [tenant["name"] for tenant in tenants_and_organizations["tenants"]]
    console.display_options(tenant_names, "Select tenant:")
    tenant_idx = (
        0
        if len(tenant_names) == 1
        else console.prompt("Select tenant number", type=int)
    )
    tenant_name = tenant_names[tenant_idx]
    account_name = tenants_and_organizations["organization"]["name"]
    console.info(f"Selected tenant: {click.style(tenant_name, fg='cyan')}")

    update_env_file(
        {
            "UIPATH_URL": f"https://{domain if domain else 'alpha'}.uipath.com/{account_name}/{tenant_name}",
            "UIPATH_TENANT_ID": tenants_and_organizations["tenants"][tenant_idx]["id"],
            "UIPATH_ORGANIZATION_ID": tenants_and_organizations["organization"]["id"],
        }
    )

    return f"https://{domain if domain else 'alpha'}.uipath.com/{account_name}/{tenant_name}"
