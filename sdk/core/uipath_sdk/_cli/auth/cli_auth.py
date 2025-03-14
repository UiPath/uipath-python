import webbrowser

import click
from dotenv import load_dotenv

from .._common_cli_utils import environment_options
from ._auth_server import HTTPSServer
from ._models import TenantsAndOrganizationInfoResponse
from ._oidc_utils import get_auth_config, get_auth_url
from ._portal_service import PortalService
from ._utils import update_auth_file, update_env_file

load_dotenv()


def select_tenant(
    domain, tenants_and_organizations: TenantsAndOrganizationInfoResponse
):
    tenant_names = [tenant["name"] for tenant in tenants_and_organizations["tenants"]]
    click.echo("Available tenants:")
    for idx, name in enumerate(tenant_names):
        click.echo(f"  {idx}: {name}")
    tenant_idx = click.prompt("Select tenant", type=int)
    tenant_name = tenant_names[tenant_idx]
    account_name = tenants_and_organizations["organization"]["name"]
    click.echo(f"Selected tenant: {tenant_name}")

    update_env_file(
        {"UIPATH_URL": f"https://{domain}.uipath.com/{account_name}/{tenant_name}"}
    )


@click.command()
@environment_options
def auth(domain="alpha"):
    """Authenticate with UiPath Cloud Platform"""
    portal_service = PortalService(domain)
    try:
        portal_service.ensure_valid_token()
        click.echo("Authentication successful")
        return
    except Exception:
        click.echo("Authentication not found or expired. Please authenticate again.")

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
