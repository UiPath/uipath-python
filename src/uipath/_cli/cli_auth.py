# type: ignore
import asyncio
import json
import os
import socket
import webbrowser

import click
from dotenv import load_dotenv

from ..telemetry import track
from ._auth._auth_server import HTTPServer
from ._auth._client_credentials import ClientCredentialsService
from ._auth._oidc_utils import get_auth_config, get_auth_url
from ._auth._portal_service import PortalService, select_tenant
from ._auth._utils import update_auth_file, update_env_file
from ._utils._common import environment_options
from ._utils._console import ConsoleLogger

load_dotenv(override=True)
console = ConsoleLogger()


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            s.close()
            return False
        except socket.error:
            return True


def set_port():
    auth_config = get_auth_config()
    port = auth_config.get("port", 8104)
    port_option_one = auth_config.get("portOptionOne", 8104)
    port_option_two = auth_config.get("portOptionTwo", 8055)
    port_option_three = auth_config.get("portOptionThree", 42042)
    if is_port_in_use(port):
        if is_port_in_use(port_option_one):
            if is_port_in_use(port_option_two):
                if is_port_in_use(port_option_three):
                    console.error(
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


@click.command()
@environment_options
@click.option(
    "-f",
    "--force",
    is_flag=True,
    required=False,
    help="Force new token",
)
@click.option(
    "--client-id",
    required=False,
    help="Client ID for client credentials authentication (unattended mode)",
)
@click.option(
    "--client-secret",
    required=False,
    help="Client secret for client credentials authentication (unattended mode)",
)
@click.option(
    "--base-url",
    required=False,
    help="Base URL for the UiPath tenant instance (required for client credentials)",
)
@track
def auth(
    domain,
    force: None | bool = False,
    client_id: str = None,
    client_secret: str = None,
    base_url: str = None,
):
    """Authenticate with UiPath Cloud Platform.

    Interactive mode (default): Opens browser for OAuth authentication.
    Unattended mode: Use --client-id, --client-secret and --base-url for client credentials flow.

    Network options:
    - Set HTTP_PROXY/HTTPS_PROXY/NO_PROXY environment variables for proxy configuration
    - Set REQUESTS_CA_BUNDLE to specify a custom CA bundle for SSL verification
    - Set UIPATH_DISABLE_SSL_VERIFY to disable SSL verification (not recommended)
    """
    # Check if client credentials are provided for unattended authentication
    if client_id and client_secret:
        if not base_url:
            console.error(
                "--base-url is required when using client credentials authentication."
            )
            return

        with console.spinner("Authenticating with client credentials ..."):
            credentials_service = ClientCredentialsService(domain)

            # If base_url is provided, extract domain from it to override the CLI domain parameter
            if base_url:
                extracted_domain = credentials_service.extract_domain_from_base_url(
                    base_url
                )
                credentials_service.domain = extracted_domain

            token_data = credentials_service.authenticate(client_id, client_secret)

            if token_data:
                credentials_service.setup_environment(token_data, base_url)
                console.success(
                    "Client credentials authentication successful.",
                )
            else:
                console.error(
                    "Client credentials authentication failed. Please check your credentials.",
                )
        return

    # Interactive authentication flow (existing logic)
    with console.spinner("Authenticating with UiPath ..."):
        with PortalService(domain) as portal_service:
            if not force:
                if (
                    os.getenv("UIPATH_URL")
                    and os.getenv("UIPATH_TENANT_ID")
                    and os.getenv("UIPATH_ORGANIZATION_ID")
                ):
                    try:
                        portal_service.ensure_valid_token()
                        console.success(
                            "Authentication successful.",
                        )
                        return
                    except Exception:
                        console.info(
                            "Authentication token is invalid. Please reauthenticate.",
                        )

            auth_url, code_verifier, state = get_auth_url(domain)

            webbrowser.open(auth_url, 1)
            auth_config = get_auth_config()

            console.link(
                "If a browser window did not open, please open the following URL in your browser:",
                auth_url,
            )

            try:
                server = HTTPServer(port=auth_config["port"])
                token_data = asyncio.run(server.start(state, code_verifier, domain))

                if not token_data:
                    console.error(
                        "Authentication failed. Please try again.",
                    )
                    return

                portal_service.update_token_data(token_data)
                update_auth_file(token_data)
                access_token = token_data["access_token"]
                update_env_file({"UIPATH_ACCESS_TOKEN": access_token})

                tenants_and_organizations = (
                    portal_service.get_tenants_and_organizations()
                )
                base_url = select_tenant(domain, tenants_and_organizations)
                try:
                    portal_service.post_auth(base_url)
                    console.success(
                        "Authentication successful.",
                    )
                except Exception:
                    console.error(
                        "Could not prepare the environment. Please try again.",
                    )
            except KeyboardInterrupt:
                console.error(
                    "Authentication cancelled by user.",
                )
