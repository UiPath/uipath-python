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


def get_available_feeds(
    base_url: str, headers: dict[str, str]
) -> list[tuple[str, str]]:
    url = f"{base_url}/orchestrator_/api/PackageFeeds/GetFeeds"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        click.echo(
            f"❌ Failed to fetch available feeds. Status code: {response.status_code}"
        )
        if response.text:
            click.echo(response.text)
        click.get_current_context().exit(1)
    try:
        available_feeds = [
            feed for feed in response.json() if feed["purpose"] == "Processes"
        ]
        return [(feed["name"], feed["id"]) for feed in available_feeds]
    except Exception as e:
        click.echo(
            "❌ Failed to deserialize available feeds.",
        )
        click.echo(e)
        click.get_current_context().exit(1)


@click.command()
@click.option(
    "--tenant",
    "-t",
    "feed",
    flag_value="tenant",
    help="Whether to publish to the tenant package feed",
)
@click.option(
    "--my-workspace",
    "-w",
    "feed",
    flag_value="personal",
    help="Whether to publish to the personal workspace",
)
def publish(feed):
    spinner = Spinner()
    current_path = os.getcwd()
    load_dotenv(os.path.join(current_path, ".env"), override=True)
    [base_url, token] = get_env_vars()
    headers = {"Authorization": f"Bearer {token}"}
    if feed is None:
        available_feeds = get_available_feeds(base_url, headers)
        click.echo("👇 Select package feed:")
        for idx, feed in enumerate(available_feeds, start=0):
            click.echo(f"  {idx}: {feed[0]}")
        feed_idx = click.prompt("Select feed", type=int)
        if feed_idx < 0:
            click.echo("❌ Invalid input")
            click.get_current_context().exit(1)
        try:
            selected_feed = available_feeds[feed_idx]
            feed = selected_feed[1]
        except IndexError:
            click.echo("❌ Invalid feed selected")
            click.get_current_context().exit(1)

        click.echo(f"Selected feed: {click.style(str(selected_feed[0]), fg='cyan')}")

    os.makedirs(".uipath", exist_ok=True)

    # Find most recent .nupkg file in .uipath directory
    most_recent = get_most_recent_package()

    if not most_recent:
        spinner.stop()
        click.echo("❌ Error: No package files found in .uipath directory")
        raise click.Abort()

    spinner.start(f"Publishing most recent package: {most_recent}")

    package_to_publish_path = os.path.join(".uipath", most_recent)

    url = f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()"
    is_personal_workspace = False

    if feed and feed != "tenant":
        # Check user personal workspace
        personal_workspace_feed_id, personal_workspace_folder_id = (
            get_personal_workspace_info(base_url, token, spinner)
        )
        if feed == "personal" or feed == personal_workspace_feed_id:
            is_personal_workspace = True
            url = url + "?feedId=" + personal_workspace_feed_id
        else:
            url = url + "?feedId=" + feed

    with open(package_to_publish_path, "rb") as f:
        files = {"file": (package_to_publish_path, f, "application/octet-stream")}
        response = requests.post(url, headers=headers, files=files)

    spinner.stop()

    if response.status_code == 200:
        click.echo(
            click.style("✓ ", fg="green", bold=True) + "Package published successfully!"
        )
        if is_personal_workspace:
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
                    "🔧 Configure your process: "
                    + click.style(
                        f"\u001b]8;;{process_url}\u001b\\{process_url}\u001b]8;;\u001b\\",
                        fg="bright_blue",
                        bold=True,
                    )
                )
                click.echo(
                    "💡 Use the link above to configure any environment variables"
                )
            else:
                click.echo("⚠️ Warning: Failed to compose process url")
    else:
        click.echo(f"❌ Failed to publish package. Status code: {response.status_code}")
        if response.text:
            click.echo(response.text)
