# type: ignore
import os
import webbrowser

import click
from dotenv import load_dotenv

from uipath_sdk._cli._auth._auth_server import HTTPSServer
from uipath_sdk._cli._auth._oidc_utils import get_auth_config, get_auth_url
from uipath_sdk._cli._auth._portal_service import PortalService, select_tenant
from uipath_sdk._cli._auth._utils import update_auth_file, update_env_file
from uipath_sdk._cli._utils._common import environment_options

load_dotenv()


@click.command()
@environment_options
def auth(domain="alpha"):
    """Authenticate with UiPath Cloud Platform"""
    portal_service = PortalService(domain)
    if os.getenv("UIPATH_URL"):
        try:
            portal_service.ensure_valid_token()
            click.echo("Authentication successful")
            return
        except Exception:
            click.echo(
                "Authentication not found or expired. Please authenticate again."
            )

    auth_url, code_verifier, state = get_auth_url(domain)

    webbrowser.open(auth_url, 1)
    auth_config = get_auth_config()

    server = HTTPSServer(port=auth_config["port"])
    token_data = server.start(state, code_verifier)
    try:
        if token_data:
            portal_service.update_token_data(token_data)
            update_auth_file(token_data)
            access_token = token_data["access_token"]
            update_env_file({"UIPATH_ACCESS_TOKEN": access_token})

            tenants_and_organizations = portal_service.get_tenants_and_organizations()
            select_tenant(domain, tenants_and_organizations)
        else:
            click.echo("Authentication failed")
    except Exception as e:
        click.echo(f"Authentication failed: {e}")
