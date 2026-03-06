import os
import webbrowser
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, error, socket
from typing import Any

import click

from uipath._cli._auth._auth_server import HTTPServer
from uipath._cli._utils._console import ConsoleLogger
from uipath.platform import UiPath
from uipath.platform.auth import (
    AuthService,
    TenantsAndOrganizationInfoResponse,
    extract_org_tenant,
    get_auth_data,
    get_parsed_token_data,
    resolve_domain,
    update_auth_file,
)
from uipath.platform.common import ExternalApplicationService, TokenData


def _find_free_port(candidates: list[int]) -> int | None:
    """Find the first free port from the given candidates."""

    def is_free(port: int) -> bool:
        with socket(AF_INET, SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return True
            except error:
                return False

    return next((p for p in candidates if is_free(p)), None)


def _get_redirect_uri_and_port() -> tuple[str, int]:
    """Resolve a free port and build the redirect URI."""
    custom_port = os.getenv("UIPATH_AUTH_PORT")
    candidates = [int(custom_port)] if custom_port else [8104, 8055, 42042]

    port = _find_free_port(candidates)
    if port is None:
        ports_str = ", ".join(str(p) for p in candidates)
        raise ValueError(
            f"All configured ports ({ports_str}) are in use. "
            "Please close applications using these ports or configure different ports via UIPATH_AUTH_PORT."
        )

    redirect_uri = f"http://localhost:{port}/oidc/login"
    return redirect_uri, port


def update_env_file(env_contents: dict[str, Any]) -> None:
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    if key not in env_contents:
                        env_contents[key] = value
    lines = [f"{key}={value}\n" for key, value in env_contents.items()]
    with open(env_path, "w") as f:
        f.writelines(lines)


class AuthHandler:
    def __init__(
        self,
        environment: str | None,
        *,
        force: bool,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        tenant: str | None = None,
        scope: str | None = None,
    ):
        self._force = force
        self._console = ConsoleLogger()
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._tenant = tenant
        self._domain = resolve_domain(self._base_url, environment)
        self._scope = scope
        self._auth_service = AuthService(self._domain)

    async def authenticate(self) -> None:
        if self._client_id and self._client_secret:
            await self._authenticate_client_credentials()
            return

        await self._authenticate_authorization_code()

    async def _authenticate_client_credentials(self):
        assert self._client_id and self._client_secret, (
            "Client ID and Client Secret must be provided."
        )
        external_app_service = ExternalApplicationService(self._base_url)
        token_data = external_app_service.get_token_data(
            self._client_id,
            self._client_secret,
            self._scope,
        )

        organization_name, tenant_name = extract_org_tenant(
            external_app_service._base_url
        )
        if not (organization_name and tenant_name):
            self._console.warning(
                "--base-url should include both organization and tenant, "
                "e.g., 'https://cloud.uipath.com/{organization}/{tenant}'."
            )

        env_vars = {
            "UIPATH_ACCESS_TOKEN": token_data.access_token,
            "UIPATH_URL": external_app_service._base_url,
            "UIPATH_ORGANIZATION_ID": get_parsed_token_data(token_data).get("prt_id"),
        }

        if tenant_name:
            self._tenant = tenant_name
            data = await self._auth_service.get_tenants_and_organizations(
                token_data.access_token
            )
            tenant_info = self._find_tenant(data, self._tenant)
            env_vars["UIPATH_TENANT_ID"] = tenant_info["tenant_id"]
        else:
            self._console.warning("Could not extract tenant from --base-url.")
        update_env_file(env_vars)

    async def _authenticate_authorization_code(self) -> None:
        if not self._force and await self._can_reuse_existing_token():
            return

        token_data = await self._perform_oauth_flow()
        update_auth_file(token_data)

        data = await self._auth_service.get_tenants_and_organizations(
            token_data.access_token
        )
        tenant_info = await self._resolve_tenant_info(data, self._tenant)
        organization_name = data["organization"]["name"]
        uipath_url = f"{self._domain}/{organization_name}/{tenant_info['tenant_name']}"

        update_env_file(
            {
                "UIPATH_ACCESS_TOKEN": token_data.access_token,
                "UIPATH_URL": uipath_url,
                "UIPATH_TENANT_ID": tenant_info["tenant_id"],
                "UIPATH_ORGANIZATION_ID": tenant_info["organization_id"],
            }
        )

        try:
            client = UiPath(base_url=uipath_url, secret=token_data.access_token)
            await client.studio_web.enable_async()
        except Exception:
            self._console.error("Could not prepare the environment. Please try again.")

    async def _can_reuse_existing_token(self) -> bool:
        if (
            os.getenv("UIPATH_URL")
            and os.getenv("UIPATH_TENANT_ID")
            and os.getenv("UIPATH_ORGANIZATION_ID")
        ):
            try:
                auth_data = get_auth_data()
                token_data = await self._auth_service.ensure_valid_token(auth_data)
                if token_data is not auth_data:
                    update_auth_file(token_data)
                update_env_file({"UIPATH_ACCESS_TOKEN": token_data.access_token})
                return True
            except Exception:
                self._console.error(
                    "Authentication token is invalid. Please reauthenticate using the '--force' flag."
                )
        return False

    async def _perform_oauth_flow(self) -> TokenData:
        redirect_uri, port = _get_redirect_uri_and_port()
        auth_request = self._auth_service.get_authorization_url(redirect_uri)
        self._open_browser(auth_request.url)

        server = HTTPServer(
            port=port,
            redirect_uri=redirect_uri,
            client_id=self._auth_service.auth_config.client_id,
        )
        token_data = await server.start(
            auth_request.state, auth_request.code_verifier, self._domain
        )

        if not token_data:
            self._console.error(
                "Authentication failed. Please try again.",
            )

        return TokenData.model_validate(token_data)

    async def _resolve_tenant_info(
        self, data: TenantsAndOrganizationInfoResponse, tenant: str | None
    ) -> dict[str, Any]:
        if tenant:
            return self._find_tenant(data, tenant)
        return self._select_tenant(data)

    def _find_tenant(
        self, data: TenantsAndOrganizationInfoResponse, tenant_name: str
    ) -> dict[str, Any]:
        """Find a tenant by name from the tenants/org response."""
        organization = data["organization"]
        tenants = data["tenants"]
        tenant = next((t for t in tenants if t["name"] == tenant_name), None)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_name}' not found.")
        return {
            "tenant_id": tenant["id"],
            "organization_id": organization["id"],
            "tenant_name": tenant["name"],
        }

    def _select_tenant(
        self, data: TenantsAndOrganizationInfoResponse
    ) -> dict[str, Any]:
        """Interactively select a tenant from the list."""
        organization = data["organization"]
        tenants = data["tenants"]
        tenant_names = [t["name"] for t in tenants]

        self._console.display_options(tenant_names, "Select tenant:")
        tenant_idx = (
            0
            if len(tenant_names) == 1
            else self._console.prompt("Select tenant number", type=int)
        )

        tenant = tenants[tenant_idx]
        self._console.info(f"Selected tenant: {click.style(tenant['name'], fg='cyan')}")
        return {
            "tenant_id": tenant["id"],
            "organization_id": organization["id"],
            "tenant_name": tenant["name"],
        }

    def _open_browser(self, url: str) -> None:
        webbrowser.open(url, new=1)
        self._console.link(
            "If a browser window did not open, please open the following URL in your browser:",
            url,
        )
