# type: ignore
import json
import os

import click
import requests
from dotenv import load_dotenv

from ._utils._common import get_env_vars
from ._utils._folders import get_personal_workspace_info
from ._utils._processes import get_release_info
from .spinner import Spinner


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
    spinner = Spinner()
    current_path = os.getcwd()
    load_dotenv(os.path.join(current_path, ".env"), override=True)
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
        spinner.stop()
        click.echo("❌ Error: No package files found in .uipath directory")
        raise click.Abort()

    spinner.start(f"Publishing most recent package: {most_recent}")

    package_to_publish_path = os.path.join(".uipath", most_recent)

    [base_url, token] = get_env_vars(spinner)

    url = f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()"

    if feed == "personal":
        # Get current user extended info to get personal workspace ID
        personal_workspace_feed_id, personal_workspace_folder_id = (
            get_personal_workspace_info(base_url, token, spinner)
        )

        url = url + "?feedId=" + personal_workspace_feed_id

    headers = {"Authorization": f"Bearer {token}"}

    with open(package_to_publish_path, "rb") as f:
        files = {"file": (package_to_publish_path, f, "application/octet-stream")}
        response = requests.post(url, headers=headers, files=files)

    spinner.stop()

    if response.status_code == 200:
        click.echo(
            click.style("✓ ", fg="green", bold=True) + "Package published successfully!"
        )
        if feed == "personal":
            try:
                data = json.loads(response.text)
                package_name = json.loads(data["value"][0]["Body"])["Id"]
            except json.decoder.JSONDecodeError:
                click.echo("⚠️ Warning: Failed to deserialize package name")
                raise click.Abort() from json.decoder.JSONDecodeError
            release_id, _ = get_release_info(
                base_url, token, package_name, personal_workspace_feed_id, spinner
            )
            if release_id:
                process_url = f"{base_url}/orchestrator_/processes/{release_id}/edit?fid={personal_workspace_folder_id}"
                click.echo(
                    "\n🔧 Configure your process: "
                    + click.style(
                        f"\u001b]8;;{process_url}\u001b\\{process_url}\u001b]8;;\u001b\\",
                        fg="bright_blue",
                        bold=True,
                    )
                )
                click.echo(
                    "\n💡 Use the link above to configure any environment variables\n"
                )
            else:
                click.echo("⚠️ Warning: Failed to compose process url")
    else:
        click.echo(f"❌ Failed to publish package. Status code: {response.status_code}")
        if response.text:
            click.echo(response.text)
