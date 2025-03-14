# type: ignore
import os

import click
import requests
from dotenv import load_dotenv

from ._auth.cli_auth import PortalService, auth
from ._common_cli_utils import environment_options


def get_most_recent_package():
    nupkg_files = [f for f in os.listdir(".uipath") if f.endswith(".nupkg")]
    if not nupkg_files:
        click.echo("No .nupkg file found in .uipath directory")
        return

    # Get full path and modification time for each file
    nupkg_files_with_time = [
        (f, os.path.getmtime(os.path.join(".uipath", f))) for f in nupkg_files
    ]

    # Sort by modification time (most recent first)
    nupkg_files_with_time.sort(key=lambda x: x[1], reverse=True)

    # Get most recent file
    return nupkg_files_with_time[0][0]


def get_env_vars():
    load_dotenv(os.path.join(os.getcwd(), ".env"))

    base_url = os.environ.get("UIPATH_URL")
    token = os.environ.get("UIPATH_ACCESS_TOKEN")

    if not all([base_url, token]):
        click.echo(
            "Missing required environment variables. Please check your .env file contains:"
        )
        click.echo("UIPATH_URL, UIPATH_ACCESS_TOKEN")
        raise click.Abort("Missing environment variables")

    return [base_url, token]


@click.command()
@environment_options
def publish(domain="alpha"):
    os.makedirs(".uipath", exist_ok=True)
    portal_service = PortalService(domain)
    if not portal_service.has_initialized_auth():
        click.echo("No valid authentication found. Please authenticate.")
        ctx = click.get_current_context()
        ctx.invoke(auth)
    # Find most recent .nupkg file in .uipath directory
    most_recent = get_most_recent_package()

    click.echo(f"Publishing most recent package: {most_recent}")

    package_to_publish_path = os.path.join(".uipath", most_recent)

    [base_url, token] = get_env_vars()

    url = f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()"

    headers = {"Authorization": f"Bearer {token}"}

    with open(package_to_publish_path, "rb") as f:
        files = {"file": (package_to_publish_path, f, "application/octet-stream")}
        response = requests.post(url, headers=headers, files=files)

    if response.status_code == 200:
        click.echo("Package published successfully!")
    else:
        click.echo(f"Failed to publish package. Status code: {response.status_code}")
        click.echo(f"Response: {response.text}")
