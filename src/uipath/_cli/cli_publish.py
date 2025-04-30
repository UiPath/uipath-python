# type: ignore
import json
import os

import click
import httpx
from dotenv import load_dotenv

from ._utils._common import get_env_vars
from ._utils._console import ConsoleLogger
from ._utils._folders import get_personal_workspace_info
from ._utils._processes import get_release_info

console = ConsoleLogger()
client = httpx.Client(follow_redirects=True)


def get_most_recent_package():
    nupkg_files = [f for f in os.listdir(".uipath") if f.endswith(".nupkg")]
    if not nupkg_files:
        console.error("No .nupkg files found. Please run `uipath pack` first.")
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
    response = httpx.get(url, headers=headers)
    if response.status_code != 200:
        console.error(
            f"Failed to fetch available feeds. Please check your connection. Status code: {response.status_code} {response.text}"
        )
    try:
        available_feeds = [
            feed for feed in response.json() if feed["purpose"] == "Processes"
        ]
        return [(feed["name"], feed["id"]) for feed in available_feeds]
    except Exception as e:
        console.error(f"Failed to deserialize available feeds: {str(e)}")


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
    """Publish the package."""
    current_path = os.getcwd()
    load_dotenv(os.path.join(current_path, ".env"), override=True)

    [base_url, token] = get_env_vars()
    headers = {"Authorization": f"Bearer {token}"}

    if feed is None:
        with console.spinner("Fetching available package feeds..."):
            available_feeds = get_available_feeds(base_url, headers)
        console.display_options(
            [feed[0] for feed in available_feeds], "Select package feed:"
        )
        feed_idx = console.prompt("Select feed number", type=int)
        if feed_idx < 0:
            console.error("Invalid feed selected")
        try:
            selected_feed = available_feeds[feed_idx]
            feed = selected_feed[1]
            console.info(
                f"Selected feed: {click.style(str(selected_feed[0]), fg='cyan')}"
            )
        except IndexError:
            console.error("Invalid feed selected")

    os.makedirs(".uipath", exist_ok=True)

    # Find most recent .nupkg file in .uipath directory
    most_recent = get_most_recent_package()

    if not most_recent:
        console.error("No .nupkg files found. Please run `uipath pack` first.")

    is_personal_workspace = False

    with console.spinner(f"Publishing most recent package: {most_recent} ..."):
        package_to_publish_path = os.path.join(".uipath", most_recent)
        url = f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()"

        if feed and feed != "tenant":
            # Check user personal workspace
            personal_workspace_feed_id, personal_workspace_folder_id = (
                get_personal_workspace_info(base_url, token)
            )
            if feed == "personal" or feed == personal_workspace_feed_id:
                is_personal_workspace = True
                if (
                    personal_workspace_feed_id is None
                    or personal_workspace_folder_id is None
                ):
                    console.error(
                        "No personal workspace found for user. Please try reauthenticating."
                    )
                url = url + "?feedId=" + personal_workspace_feed_id
            else:
                url = url + "?feedId=" + feed

        with open(package_to_publish_path, "rb") as f:
            files = {"file": (package_to_publish_path, f, "application/octet-stream")}
            response = client.post(url, headers=headers, files=files)

    if response.status_code == 200:
        console.success("Package published successfully!")

        if is_personal_workspace:
            try:
                data = json.loads(response.text)
                package_name = json.loads(data["value"][0]["Body"])["Id"]
            except json.decoder.JSONDecodeError:
                console.warning("Failed to deserialize package name")
            if package_name is not None:
                with console.spinner("Getting process information ..."):
                    release_id, _ = get_release_info(
                        base_url, token, package_name, personal_workspace_feed_id
                    )
                if release_id:
                    process_url = f"{base_url}/orchestrator_/processes/{release_id}/edit?fid={personal_workspace_folder_id}"
                    console.link("Process configuration link:", process_url)
                    console.hint(
                        "Use the link above to configure any environment variables"
                    )
                else:
                    console.warning("Failed to compose process url")
    else:
        console.error(
            f"Failed to publish package. Status code: {response.status_code} {response.text}"
        )
