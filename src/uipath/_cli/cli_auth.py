# type: ignore
import json
import logging
import os
import socket
import webbrowser

import click
from dotenv import load_dotenv

from .._utils._logs import setup_logging
from ._auth._auth_server import HTTPSServer
from ._auth._oidc_utils import get_auth_config, get_auth_url
from ._auth._portal_service import PortalService, select_tenant
from ._auth._utils import update_auth_file, update_env_file
from ._utils._common import environment_options

logger = logging.getLogger(__name__)

load_dotenv()


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

    logger.debug(f"Checking port availability. Initial port: {port}")

    if is_port_in_use(port):
        logger.debug(f"Port {port} is in use, trying alternatives")
        if is_port_in_use(port_option_one):
            if is_port_in_use(port_option_two):
                if is_port_in_use(port_option_three):
                    logger.error("All configured ports are in use")
                    raise RuntimeError(
                        "All configured ports are in use. Please close applications using ports or configure different ports."
                    )
                else:
                    port = port_option_three
                    logger.debug(f"Using port option three: {port}")
            else:
                port = port_option_two
                logger.debug(f"Using port option two: {port}")
        else:
            port = port_option_one
            logger.debug(f"Using port option one: {port}")
    else:
        logger.debug(f"Using initial port: {port}")

    auth_config["port"] = port
    config_path = os.path.join(os.path.dirname(__file__), "..", "auth_config.json")
    logger.debug(f"Updating auth config at: {config_path}")
    with open(config_path, "w") as f:
        json.dump(auth_config, f)


@click.command()
@environment_options
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def auth(domain="alpha", verbose=False):
    """Authenticate with UiPath Cloud Platform."""
    # Setup logging based on verbose flag
    setup_logging(should_debug=verbose)

    logger.debug(f"Starting authentication process for domain: {domain}")
    portal_service = PortalService(domain)

    if (
        os.getenv("UIPATH_URL")
        and os.getenv("UIPATH_TENANT_ID")
        and os.getenv("UIPATH_ORGANIZATION_ID")
    ):
        logger.debug("Checking existing authentication")
        try:
            portal_service.ensure_valid_token()
            logger.info("Authentication successful")
            return
        except Exception as e:
            logger.warning(f"Existing authentication invalid: {str(e)}")
            logger.info(
                "Authentication not found or expired. Please authenticate again."
            )

    logger.debug("Generating auth URL")
    auth_url, code_verifier, state = get_auth_url(domain)

    logger.debug("Opening browser for authentication")
    webbrowser.open(auth_url, 1)
    auth_config = get_auth_config()

    logger.info(
        "If a browser window did not open, please open the following URL in your browser:"
    )
    logger.info(auth_url)

    logger.debug("Starting auth server")
    server = HTTPSServer(port=auth_config["port"])
    token_data = server.start(state, code_verifier, domain)

    try:
        if token_data:
            logger.debug("Token received, updating services")
            portal_service.update_token_data(token_data)
            update_auth_file(token_data)
            access_token = token_data["access_token"]
            update_env_file({"UIPATH_ACCESS_TOKEN": access_token})

            logger.debug("Fetching tenants and organizations")
            tenants_and_organizations = portal_service.get_tenants_and_organizations()
            select_tenant(domain, tenants_and_organizations)
            logger.info("Authentication completed successfully")
        else:
            logger.error("No token data received")
            click.echo("Authentication failed")
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        click.echo(f"Authentication failed: {e}")
