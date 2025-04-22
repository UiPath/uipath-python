import os
import click
import json
from typing import Optional, TYPE_CHECKING
import requests
from dotenv import load_dotenv
from ._auth._utils import update_env_file

if TYPE_CHECKING:
    pass

def get_env_vars():
    base_url = os.environ.get("UIPATH_URL")
    tenant_id = os.environ.get("UIPATH_TENANT_ID")
    token = os.environ.get("UIPATH_ACCESS_TOKEN")
    package_key = os.environ.get("UIPATH_PACKAGE_KEY")
    package_version = os.environ.get("UIPATH_PACKAGE_VERSION")
    

    if not all([base_url, tenant_id, token, package_key, package_version]):
        click.echo(
            "Missing required environment variables. Please check your .env file contains:"
        )
        click.echo("UIPATH_URL, UIPATH_TENANT_ID, UIPATH_ACCESS_TOKEN, UIPATH_PACKAGE_KEY")
        raise click.Abort("Missing environment variables")

    return [base_url, tenant_id, token, package_key, package_version]

@click.command()
@click.option("--action", is_flag=True, help="Create an action app")
def app(action: bool = False) -> None:
    """
    Creates a new UiPath App. (Placeholder)
    """
    click.echo("Placeholder for creating a new UiPath App.")
    # Get base url, token, package key from env variables, make that a function
    base_url, tenant_id, token, package_key, package_version = get_env_vars()
    url = f"{base_url}/default/api/v1/default/models/tenants/{tenant_id}/publish/extenal/apps"

    headers = {"Authorization": f"Bearer {token}"}

    # Construct path relative to the current working directory
    current_dir = os.getcwd()
    metadata_path = os.path.join(current_dir, "metadata.json")

    # Read schema from metadata.json
    try:
        with open(metadata_path, 'r') as f:
            schema_data = json.load(f)
    except FileNotFoundError:
        click.echo(f"Error: metadata.json not found at {metadata_path}")
        raise click.Abort()
    except json.JSONDecodeError:
        click.echo(f"Error: Could not decode JSON from {metadata_path}")
        raise click.Abort()

    payload = {
        "name": package_key,
        "title": package_key,
        "version": package_version,
        "context": {
            "appUsageType": "1" if action else "0"
        },
        "schema": schema_data
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        click.echo("App Created successfully!")
        click.echo(response.json())
    else:
        click.echo(f"Failed to create app. Status code: {response.status_code}")
        click.echo(f"Response: {response.text}")
    
