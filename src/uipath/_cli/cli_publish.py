# type: ignore
import json
import logging
import os

import click
import requests
from dotenv import load_dotenv

from .._utils._logs import setup_logging

logger = logging.getLogger(__name__)


def get_most_recent_package():
    nupkg_files = [f for f in os.listdir(".uipath") if f.endswith(".nupkg")]
    if not nupkg_files:
        logger.warning("No .nupkg file found in .uipath directory")
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
        logger.error(
            "Missing required environment variables. Please check your .env file contains:"
        )
        logger.error("UIPATH_URL, UIPATH_ACCESS_TOKEN")
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
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def publish(feed, verbose):
    current_path = os.getcwd()
    load_dotenv(os.path.join(current_path, ".env"), override=True)
    # Setup logging based on verbose flag
    setup_logging(should_debug=verbose)

    current_path = os.getcwd()
    logger.debug(f"Current working directory: {current_path}")

    load_dotenv(os.path.join(current_path, ".env"), override=True)
    logger.debug("Loaded environment variables from .env file")

    if feed is None:
        click.echo("Select feed type:")
        click.echo("  0: Tenant package feed")
        click.echo("  1: Personal workspace")
        feed_idx = click.prompt("Select feed", type=int)
        feed = "tenant" if feed_idx == 0 else "personal"
        logger.info(f"Selected feed: {feed}")

    os.makedirs(".uipath", exist_ok=True)
    logger.debug("Ensured .uipath directory exists")

    # Find most recent .nupkg file in .uipath directory
    most_recent = get_most_recent_package()

    if not most_recent:
        logger.error("No package files found in .uipath directory")
        raise click.Abort()

    logger.info(f"Publishing most recent package: {most_recent}")
    package_to_publish_path = os.path.join(".uipath", most_recent)

    [base_url, token] = get_env_vars()
    logger.debug(f"Using base URL: {base_url}")

    url = f"{base_url}/orchestrator_/odata/Processes/UiPath.Server.Configuration.OData.UploadPackage()"

    if feed == "personal":
        logger.debug("Using personal workspace feed")
        # Get current user extended info to get personal workspace ID
        user_url = f"{base_url}/orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended"
        logger.debug(f"Fetching user info from: {user_url}")

        user_response = requests.get(
            user_url, headers={"Authorization": f"Bearer {token}"}
        )

        if user_response.status_code != 200:
            logger.error(
                f"Failed to get user info. Status code: {user_response.status_code}"
            )
            logger.error(f"Response: {user_response.text}")
            raise click.Abort()

        user_data = {}
        try:
            user_data = user_response.json()
            logger.debug("Successfully retrieved user data")
        except json.JSONDecodeError as e:
            logger.error("Failed to decode UserExtendedInfo response")
            raise click.Abort() from e

        personal_workspace_id = user_data.get("PersonalWorskpaceFeedId")

        if not personal_workspace_id:
            logger.error("No personal workspace found for user")
            raise click.Abort()

        url = url + "?feedId=" + personal_workspace_id
        logger.debug(f"Updated URL with personal workspace ID: {personal_workspace_id}")

    headers = {"Authorization": f"Bearer {token}"}
    logger.debug("Prepared request headers")

    logger.info("Uploading package...")
    with open(package_to_publish_path, "rb") as f:
        files = {"file": (package_to_publish_path, f, "application/octet-stream")}
        response = requests.post(url, headers=headers, files=files)

    if response.status_code == 200:
        logger.info("Package published successfully!")
    else:
        logger.error(f"Failed to publish package. Status code: {response.status_code}")
        logger.error(f"Response: {response.text}")
        raise click.Abort("Failed to publish package")
