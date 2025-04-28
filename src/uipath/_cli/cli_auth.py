# type: ignore
import json
import os
import socket
import webbrowser

import click
from dotenv import load_dotenv

from ._auth._auth_server import HTTPSServer
from ._auth._oidc_utils import get_auth_config, get_auth_url
from ._auth._portal_service import PortalService, select_tenant
from ._auth._utils import update_auth_file, update_env_file
from ._utils._common import environment_options
from ._utils._console import ConsoleLogger

load_dotenv()
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
def auth(domain="alpha"):
    """Authenticate with UiPath Cloud Platform."""
    with console.spinner("Authenticating with UiPath ..."):
        portal_service = PortalService(domain)
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

        server = HTTPSServer(port=auth_config["port"])
        token_data = server.start(state, code_verifier, domain)

        if token_data:
            portal_service.update_token_data(token_data)
            update_auth_file(token_data)
            access_token = token_data["access_token"]
            update_env_file({"UIPATH_ACCESS_TOKEN": access_token})

            tenants_and_organizations = portal_service.get_tenants_and_organizations()
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
        else:
            console.error(
                "Authentication failed. Please try again.",
            )
