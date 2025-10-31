import asyncio
import os
import webbrowser
from typing import Optional

from uipath._cli._auth._auth_server import HTTPServer
from uipath._cli._auth._oidc_utils import OidcUtils
from uipath._cli._auth._portal_service import (
    PortalService,
)
from uipath._cli._auth._url_utils import extract_org_tenant, resolve_domain
from uipath._cli._auth._utils import get_parsed_token_data
from uipath._cli._utils._console import ConsoleLogger
from uipath._services import ExternalApplicationService
from uipath._utils._auth import update_env_file
from uipath.models.auth import TokenData


class AuthService:
    def __init__(
        self,
        environment: Optional[str],
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
        self._domain = resolve_domain(self._base_url, environment)
        self._scope = scope

    def authenticate(self) -> None:
        if self._client_id and self._client_secret:
            self._authenticate_client_credentials()
            return

        self._authenticate_authorization_code()

    def _authenticate_client_credentials(self):
        external_app_service = ExternalApplicationService(self._base_url)
        token_data = external_app_service.get_token_data(
            self._client_id,  # type: ignore
            self._client_secret,  # type: ignore
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
            with PortalService(
                self._domain, access_token=token_data.access_token
            ) as portal_service:
                tenant_info = portal_service.resolve_tenant_info(self._tenant)
                env_vars["UIPATH_TENANT_ID"] = tenant_info["tenant_id"]
        else:
            self._console.warning("Could not extract tenant from --base-url.")
        update_env_file(env_vars)

    def _authenticate_authorization_code(self) -> None:
        with PortalService(self._domain) as portal_service:
            if not self._force and self._can_reuse_existing_token(portal_service):
                return

            token_data = self._perform_oauth_flow()
            portal_service.update_token_data(token_data)

            tenant_info = portal_service.resolve_tenant_info(self._tenant)
            uipath_url = portal_service.build_tenant_url()

            update_env_file(
                {
                    "UIPATH_ACCESS_TOKEN": token_data.access_token,
                    "UIPATH_URL": uipath_url,
                    "UIPATH_TENANT_ID": tenant_info["tenant_id"],
                    "UIPATH_ORGANIZATION_ID": tenant_info["organization_id"],
                }
            )

            try:
                portal_service.enable_studio_web(uipath_url)
            except Exception:
                self._console.error(
                    "Could not prepare the environment. Please try again."
                )

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

    def _perform_oauth_flow(self) -> TokenData:
        auth_config = OidcUtils.get_auth_config(self._domain)
        auth_url, code_verifier, state = OidcUtils.get_auth_url(
            self._domain, auth_config
        )
        self._open_browser(auth_url)

        server = HTTPServer(
            port=auth_config["port"],
            redirect_uri=auth_config["redirect_uri"],
            client_id=auth_config["client_id"],
        )
        token_data = asyncio.run(server.start(state, code_verifier, self._domain))

        if not token_data:
            self._console.error(
                "Authentication failed. Please try again.",
            )

        return TokenData.model_validate(token_data)

    def _open_browser(self, url: str) -> None:
        # Try to open browser. Always print the fallback link.
        webbrowser.open(url, new=1)
        self._console.link(
            "If a browser window did not open, please open the following URL in your browser:",
            url,
        )
