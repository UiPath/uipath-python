import asyncio
import json
import os
import webbrowser
from socket import AF_INET, SOCK_STREAM, error, socket
from typing import Optional
from urllib.parse import urlparse

from uipath._cli._auth._auth_server import HTTPServer
from uipath._cli._auth._client_credentials import ClientCredentialsService
from uipath._cli._auth._oidc_utils import OidcUtils
from uipath._cli._auth._portal_service import (
    PortalService,
    get_tenant_id,
    select_tenant,
)
from uipath._cli._auth._url_utils import set_force_flag
from uipath._cli._auth._utils import update_auth_file, update_env_file
from uipath._cli._utils._console import ConsoleLogger


class AuthService:
    def __init__(
        self,
        environment: str,
        *,
        force: bool,
        client_id: Optional[str],
        client_secret: Optional[str],
        base_url: Optional[str],
        tenant: Optional[str],
        scope: Optional[str],
    ):
        self._force = force
        self._console = ConsoleLogger()
        self._domain = self._get_domain(environment)
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._tenant = tenant
        self._scope = scope
        set_force_flag(self._force)

    def _get_domain(self, environment: str) -> str:
        # only search env var if not force authentication
        if not self._force:
            uipath_url = os.getenv("UIPATH_URL")
            if uipath_url and environment == "cloud":  # "cloud" is the default
                parsed_url = urlparse(uipath_url)
                if parsed_url.scheme and parsed_url.netloc:
                    environment = f"{parsed_url.scheme}://{parsed_url.netloc}"
                else:
                    self._console.error(
                        f"Malformed UIPATH_URL: '{uipath_url}'. Please ensure it includes both scheme and netloc (e.g., 'https://cloud.uipath.com')."
                    )
        return environment

    def authenticate(self) -> None:
        if self._client_id and self._client_secret:
            self._authenticate_client_credentials()
            return

        self._authenticate_authorization_code()

    def _authenticate_client_credentials(self) -> None:
        if not self._base_url:
            self._console.error(
                "--base-url is required when using client credentials authentication."
            )
            return
        self._console.hint("Using client credentials authentication.")
        credentials_service = ClientCredentialsService(self._base_url)
        credentials_service.authenticate(
            self._client_id,  # type: ignore
            self._client_secret,  # type: ignore
            self._scope,
        )

    def _authenticate_authorization_code(self) -> None:
        with PortalService(self._domain) as portal_service:
            if not self._force:
                # use existing env vars
                if (
                    os.getenv("UIPATH_URL")
                    and os.getenv("UIPATH_TENANT_ID")
                    and os.getenv("UIPATH_ORGANIZATION_ID")
                ):
                    try:
                        portal_service.ensure_valid_token()
                        return
                    except Exception:
                        self._console.error(
                            "Authentication token is invalid. Please reauthenticate using the '--force' flag.",
                        )
            auth_url, code_verifier, state = OidcUtils.get_auth_url(self._domain)
            webbrowser.open(auth_url, 1)
            auth_config = OidcUtils.get_auth_config()

            self._console.link(
                "If a browser window did not open, please open the following URL in your browser:",
                auth_url,
            )
            server = HTTPServer(port=auth_config["port"])
            token_data = asyncio.run(server.start(state, code_verifier, self._domain))

            if not token_data:
                self._console.error(
                    "Authentication failed. Please try again.",
                )

            portal_service.update_token_data(token_data)
            update_auth_file(token_data)
            access_token = token_data["access_token"]
            update_env_file({"UIPATH_ACCESS_TOKEN": access_token})

            tenants_and_organizations = portal_service.get_tenants_and_organizations()

            if self._tenant:
                base_url = get_tenant_id(
                    self._domain, self._tenant, tenants_and_organizations
                )
            else:
                base_url = select_tenant(self._domain, tenants_and_organizations)

            try:
                portal_service.post_auth(base_url)
            except Exception:
                self._console.error(
                    "Could not prepare the environment. Please try again.",
                )

    def set_port(self):
        def is_port_in_use(target_port: int) -> bool:
            with socket(AF_INET, SOCK_STREAM) as s:
                try:
                    s.bind(("localhost", target_port))
                    s.close()
                    return False
                except error:
                    return True

        auth_config = OidcUtils.get_auth_config()
        port = int(auth_config.get("port", 8104))
        port_option_one = int(auth_config.get("portOptionOne", 8104))  # type: ignore
        port_option_two = int(auth_config.get("portOptionTwo", 8055))  # type: ignore
        port_option_three = int(auth_config.get("portOptionThree", 42042))  # type: ignore
        if is_port_in_use(port):
            if is_port_in_use(port_option_one):
                if is_port_in_use(port_option_two):
                    if is_port_in_use(port_option_three):
                        self._console.error(
                            "All configured ports are in use. Please close applications using ports or configure different ports."
                        )
                    else:
                        port = port_option_three
                else:
                    port = port_option_two
            else:
                port = port_option_one
        auth_config["port"] = port
        with open(
            os.path.join(os.path.dirname(__file__), "..", "auth_config.json"), "w"
        ) as f:
            json.dump(auth_config, f)
