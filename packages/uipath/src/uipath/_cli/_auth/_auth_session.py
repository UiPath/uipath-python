import time

import click

from uipath.platform.common import TokenData
from uipath.platform.identity import IdentityService
from uipath.platform.portal import (
    PortalService as PlatformPortalService,
)
from uipath.platform.portal import (
    TenantsAndOrganizationInfoResponse,
)
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorCode,
    UiPathRuntimeError,
)

from ..._utils._auth import update_env_file
from .._utils._console import ConsoleLogger
from ._oidc_utils import OidcUtils
from ._utils import get_auth_data, get_parsed_token_data, update_auth_file


class AuthSession:
    """Holds auth state (tokens, tenant selection) across the CLI auth flow."""

    access_token: str | None = None
    prt_id: str | None = None
    domain: str
    selected_tenant: str | None = None

    _tenants_and_organizations: TenantsAndOrganizationInfoResponse | None = None

    def __init__(
        self,
        domain: str,
        access_token: str | None = None,
        prt_id: str | None = None,
    ):
        self.domain = domain
        self.access_token = access_token
        self.prt_id = prt_id
        self._console = ConsoleLogger()
        self._identity_service = IdentityService(domain)
        self._portal_service = PlatformPortalService(domain)
        self._tenants_and_organizations = None

    def update_token_data(self, token_data: TokenData):
        self.access_token = token_data.access_token
        self.prt_id = get_parsed_token_data(token_data).get("prt_id")

    async def get_tenants_and_organizations(self) -> TenantsAndOrganizationInfoResponse:
        if self._tenants_and_organizations is not None:
            return self._tenants_and_organizations

        if not self.prt_id or not self.access_token:
            raise ValueError(
                "Cannot fetch tenants: prt_id and access_token must be set."
            )

        try:
            self._tenants_and_organizations = (
                await self._portal_service.get_tenants_and_organizations_async(
                    prt_id=self.prt_id,
                    access_token=self.access_token,
                )
            )
            return self._tenants_and_organizations
        except Exception as e:
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code == 401:
                self._console.error("Unauthorized")
            self._console.error(f"Failed to get tenants and organizations: {e}")

    async def refresh_access_token(self, refresh_token: str) -> TokenData:
        client_id = (await OidcUtils.get_auth_config(self.domain))["client_id"]
        try:
            return await self._identity_service.refresh_access_token_async(
                refresh_token=refresh_token,
                client_id=client_id,
            )
        except Exception as e:
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code == 401:
                self._console.error("Unauthorized")
            status = resp.status_code if resp is not None else str(e)
            self._console.error(f"Failed to refresh token: {status}")

    async def ensure_valid_token(self):
        auth_data = get_auth_data()
        claims = get_parsed_token_data(auth_data)
        exp = claims.get("exp")

        def finalize(token_data: TokenData):
            self.update_token_data(token_data)
            update_auth_file(token_data)
            update_env_file({"UIPATH_ACCESS_TOKEN": token_data.access_token})

        if exp is not None and float(exp) > time.time():
            finalize(auth_data)
            return

        refresh_token = auth_data.refresh_token
        if not refresh_token:
            raise UiPathRuntimeError(
                UiPathErrorCode.EXECUTION_ERROR,
                "No refresh token found",
                "The refresh token could not be retrieved. Please retry authenticating.",
                UiPathErrorCategory.SYSTEM,
            )

        token_data = await self.refresh_access_token(refresh_token)
        finalize(token_data)

    def _set_tenant(self, tenant, organization):
        self.selected_tenant = tenant.name
        return {"tenant_id": tenant.id, "organization_id": organization.id}

    async def _select_tenant(self):
        data = await self.get_tenants_and_organizations()
        organization = data.organization
        tenants = data.tenants

        tenant_names = [t.name for t in tenants]

        self._console.display_options(tenant_names, "Select tenant:")
        tenant_idx = (
            0
            if len(tenant_names) == 1
            else self._console.prompt("Select tenant number", type=int)
        )

        tenant = data.tenants[tenant_idx]

        self._console.info(f"Selected tenant: {click.style(tenant.name, fg='cyan')}")
        return self._set_tenant(tenant, organization)

    async def _retrieve_tenant(self, tenant_name: str):
        data = await self.get_tenants_and_organizations()
        organization = data.organization
        tenants = data.tenants

        tenant = next((t for t in tenants if t.name == tenant_name), None)
        if not tenant:
            self._console.error(f"Tenant '{tenant_name}' not found.")
            raise Exception(f"Tenant '{tenant_name}' not found.")

        return self._set_tenant(tenant, organization)

    async def resolve_tenant_info(self, tenant: str | None = None):
        if tenant:
            return await self._retrieve_tenant(tenant)
        return await self._select_tenant()

    async def build_tenant_url(self) -> str:
        data = await self.get_tenants_and_organizations()
        organization_name = data.organization.name
        return f"{self.domain}/{organization_name}/{self.selected_tenant}"
