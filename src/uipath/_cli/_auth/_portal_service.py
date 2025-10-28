import time
from typing import Optional

import click
import httpx

from ..._utils._auth import update_env_file
from ..._utils._ssl_context import get_httpx_client_kwargs
from ...models.auth import TokenData
from .._runtime._contracts import (
    UiPathErrorCategory,
    UiPathErrorCode,
    UiPathRuntimeError,
)
from .._utils._console import ConsoleLogger
from ._models import OrganizationInfo, TenantInfo, TenantsAndOrganizationInfoResponse
from ._oidc_utils import OidcUtils
from ._url_utils import build_service_url
from ._utils import get_auth_data, get_parsed_token_data, update_auth_file


class PortalService:
    """Service for interacting with the UiPath Portal API."""

    access_token: Optional[str] = None
    prt_id: Optional[str] = None
    domain: str
    selected_tenant: Optional[str] = None

    _client: Optional[httpx.Client] = None
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
        self._console = ConsoleLogger()
        self._tenants_and_organizations = None
        self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(**get_httpx_client_kwargs())
        return self._client

    def close(self):
        """Explicitly close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context and close the HTTP client."""
        self.close()

    def update_token_data(self, token_data: TokenData):
        self.access_token = token_data.access_token
        self.prt_id = get_parsed_token_data(token_data).get("prt_id")
        update_auth_file(token_data)

    def get_tenants_and_organizations(
        self,
    ):
        if self._tenants_and_organizations is not None:
            return self._tenants_and_organizations

        url = build_service_url(
            self.domain,
            f"/{self.prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo",
        )
        response = self.client.get(
            url, headers={"Authorization": f"Bearer {self.access_token}"}
        )
        if response.status_code < 400:
            self._tenants_and_organizations = response.json()
            return self._tenants_and_organizations

        if response.status_code == 401:
            self._console.error("Unauthorized")

        self._console.error(
            f"Failed to get tenants and organizations: {response.status_code} {response.text}"
        )

    def refresh_access_token(self, refresh_token: str) -> TokenData:  # type: ignore
        url = build_service_url(self.domain, "/identity_/connect/token")
        client_id = OidcUtils.get_auth_config(self.domain).get("client_id")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = self.client.post(url, data=data, headers=headers)
        if response.status_code < 400:
            return TokenData.model_validate(response.json())

        if response.status_code == 401:
            self._console.error("Unauthorized")

        self._console.error(f"Failed to refresh token: {response.status_code}")

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

        def finalize(token_data: TokenData):
            self.update_token_data(token_data)
            update_env_file({"UIPATH_ACCESS_TOKEN": token_data.access_token})

        if exp is not None and float(exp) > time.time():
            finalize(auth_data)
            return

        refresh_token = auth_data.refresh_token
        if not refresh_token:
            raise UiPathRuntimeError(
                UiPathErrorCode.REFRESH_TOKEN_MISSING,
                "No refresh token found",
                "The refresh token could not be retrieved. Please retry authenticating.",
                UiPathErrorCategory.SYSTEM,
            )

        token_data = self.refresh_access_token(refresh_token)
        finalize(token_data)

    def enable_studio_web(self, base_url: str) -> None:
        or_base_url = self.build_orchestrator_url(base_url)

        urls = [
            f"{or_base_url}/api/StudioWeb/TryEnableFirstRun",
            f"{or_base_url}/api/StudioWeb/AcquireLicense",
        ]

        for url in urls:
            try:
                resp = self.client.post(
                    url, headers={"Authorization": f"Bearer {self.access_token}"}
                )
                if resp.status_code >= 400:
                    self._console.warning(f"Call to {url} failed: {resp.status_code}")
            except httpx.HTTPError as e:
                self._console.warning(
                    f"Exception during enable_studio_web request to {url}: {e}"
                )

    def _set_tenant(self, tenant: TenantInfo, organization: OrganizationInfo):
        self.selected_tenant = tenant["name"]
        return {"tenant_id": tenant["id"], "organization_id": organization["id"]}

    def _select_tenant(self):
        data = self.get_tenants_and_organizations()
        organization = data["organization"]
        tenants = data["tenants"]

        tenant_names = [tenant["name"] for tenant in tenants]

        self._console.display_options(tenant_names, "Select tenant:")
        tenant_idx = (
            0
            if len(tenant_names) == 1
            else self._console.prompt("Select tenant number", type=int)
        )

        tenant = data["tenants"][tenant_idx]

        self._console.info(f"Selected tenant: {click.style(tenant['name'], fg='cyan')}")
        return self._set_tenant(tenant, organization)

    def _retrieve_tenant(
        self,
        tenant_name: str,
    ):
        data = self.get_tenants_and_organizations()
        organization = data["organization"]
        tenants = data["tenants"]

        tenant = next((t for t in tenants if t["name"] == tenant_name), None)
        if not tenant:
            self._console.error(f"Tenant '{tenant_name}' not found.")

        return self._set_tenant(tenant, organization)  # type: ignore

    def resolve_tenant_info(self, tenant: Optional[str] = None):
        if tenant:
            return self._retrieve_tenant(tenant)
        return self._select_tenant()

    def build_tenant_url(self) -> str:
        data = self.get_tenants_and_organizations()
        organization_name = data["organization"]["name"]
        return f"{self.domain}/{organization_name}/{self.selected_tenant}"

    def build_orchestrator_url(self, base_url: str) -> str:
        if base_url:
            return f"{base_url}/orchestrator_"
        data = self.get_tenants_and_organizations()
        organization = data.get("organization")
        if organization is None:
            self._console.error("Organization not found.")
            return ""
        organization_name = organization.get("name")
        return f"{self.domain}/{organization_name}/{self.selected_tenant}/orchestrator_"
