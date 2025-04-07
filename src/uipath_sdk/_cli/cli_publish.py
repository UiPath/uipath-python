# type: ignore
import os

import click
import requests
from dotenv import load_dotenv

load_dotenv()


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
@click.option(
    "--tenant",
    "-t",
    "feed",
    flag_value="tenant",
    help="Whether to publish to the tenant package feed",
)
@click.option(
    "--personal-workspace",
    "-p",
    "feed",
    flag_value="personal",
    help="Whether to publish to the personal workspace",
)
def publish(feed):
    if feed is None:
        click.echo("Select feed type:")
        click.echo("  0: Tenant package feed")
        click.echo("  1: Personal workspace")
        feed_idx = click.prompt("Select feed", type=int)
        feed = "tenant" if feed_idx == 0 else "personal"
        click.echo(f"Selected feed: {feed}")
    os.makedirs(".uipath", exist_ok=True)

    # Find most recent .nupkg file in .uipath directory
    most_recent = get_most_recent_package()

    if not most_recent:
        click.echo("Error: No package files found in .uipath directory")
        raise click.Abort()
    click.echo(f"Publishing most recent package: {most_recent}")

    package_to_publish_path = os.path.join(".uipath", most_recent)

    [base_url, token] = get_env_vars()

    url = f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()"

    if feed == "personal":
        # Get current user extended info to get personal workspace ID
        user_url = f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended"
        user_response = requests.get(
            user_url, headers={"Authorization": f"Bearer {token}"}
        )

        if user_response.status_code != 200:
            click.echo("Failed to get user info")
            click.echo(f"Response: {user_response.text}")
            raise click.Abort()

        user_data = user_response.json()
        personal_workspace_id = user_data.get("PersonalWorskpaceFeedId")

        if not personal_workspace_id:
            click.echo("No personal workspace found for user")
            raise click.Abort()

        url = url + "?feedId=" + personal_workspace_id

    headers = {"Authorization": f"Bearer {token}"}

    with open(package_to_publish_path, "rb") as f:
        files = {"file": (package_to_publish_path, f, "application/octet-stream")}
        response = requests.post(url, headers=headers, files=files)

    if response.status_code == 200:
        click.echo("Package published successfully!")
    else:
        click.echo(f"Failed to publish package. Status code: {response.status_code}")
        click.echo(f"Response: {response.text}")
