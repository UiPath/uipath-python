import asyncio
import os
import webbrowser
from typing import Optional

from uipath._cli._auth._auth_server import HTTPServer
from uipath._cli._auth._models import TokenData
from uipath._cli._auth._oidc_utils import OidcUtils
from uipath._cli._auth._portal_service import PortalService
from uipath._cli._auth._url_utils import extract_org_tenant, resolve_domain
from uipath._cli._auth._utils import update_env_file
from uipath._cli._utils._console import ConsoleLogger
from uipath._services import ExternalApplicationService


class AuthService:
    def __init__(
        self,
        environment: str,
        *,
        force: bool,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        tenant: Optional[str] = None,
        scope: Optional[str] = None,
    ):
        self._force = force
        self._console = ConsoleLogger()
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._tenant = tenant
        self._domain = resolve_domain(self._base_url, environment, self._force)
        self._scope = scope

    def authenticate(self) -> None:
        if self._client_id and self._client_secret:
            self._authenticate_client_credentials()
            return

        self._authenticate_authorization_code()

    def _authenticate_client_credentials(self):
        if not self._base_url:
            self._console.error(
                "--base-url is required when using client credentials authentication."
            )
            return

        organization_name, tenant_name = extract_org_tenant(self._base_url)
        if not (organization_name and tenant_name):
            self._console.error(
                "--base-url must include both organization and tenant, "
                "e.g., 'https://cloud.uipath.com/{organization}/{tenant}'."
            )
            return

        app_service = ExternalApplicationService(self._domain)
        token_data = app_service.get_token_data(
            self._client_id,  # type: ignore
            self._client_secret,  # type: ignore
            self._scope,
        )

        self._tenant = tenant_name
        with PortalService(
            self._domain, access_token=token_data["access_token"]
        ) as portal_service:
            self._finalize_auth(portal_service, token_data)

    def _authenticate_authorization_code(self) -> None:
        with PortalService(self._domain) as portal_service:
            if not self._force and self._can_reuse_existing_token(portal_service):
                return

            auth_url, code_verifier, state = OidcUtils.get_auth_url(self._domain)
            self._open_browser(auth_url)

            auth_config = OidcUtils.get_auth_config()
            server = HTTPServer(port=auth_config["port"])
            token_data = asyncio.run(server.start(state, code_verifier, self._domain))
            if not token_data:
                self._console.error(
                    "Authentication failed. Please try again.",
                )
                return

            self._finalize_auth(portal_service, token_data)

    def _finalize_auth(
        self,
        portal_service: PortalService,
        token_data: TokenData,
    ) -> None:
        portal_service.update_token_data(token_data)

        tenant_info = (
            portal_service.retrieve_tenant(self._tenant)
            if self._tenant
            else portal_service.select_tenant()
        )

        tenant_id = tenant_info["tenant_id"]
        organization_id = tenant_info["organization_id"]
        uipath_url = portal_service.build_tenant_url()

        update_env_file(
            {
                "UIPATH_ACCESS_TOKEN": token_data["access_token"],
                "UIPATH_URL": uipath_url,
                "UIPATH_TENANT_ID": tenant_id,
                "UIPATH_ORGANIZATION_ID": organization_id,
            }
        )

        try:
            portal_service.enable_studio_web(uipath_url)
        except Exception:
            self._console.error("Could not prepare the environment. Please try again.")

    def _can_reuse_existing_token(self, portal_service: PortalService) -> bool:
        if (
            os.getenv("UIPATH_URL")
            and os.getenv("UIPATH_TENANT_ID")
            and os.getenv("UIPATH_ORGANIZATION_ID")
        ):
            try:
                portal_service.ensure_valid_token()
                return True
            except Exception:
                self._console.error(
                    "Authentication token is invalid. Please reauthenticate using the '--force' flag."
                )
        return False

    def _open_browser(self, url: str) -> None:
        # Try to open browser. Always print the fallback link.
        webbrowser.open(url, new=1)
        self._console.link(
            "If a browser window did not open, please open the following URL in your browser:",
            url,
        )
