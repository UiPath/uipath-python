# type: ignore
import asyncio
import os
from typing import Any
from urllib.parse import urlparse

import click

from ..telemetry import track
from ._push.sw_file_handler import SwFileHandler
from ._utils._console import ConsoleLogger
from ._utils._constants import (
    UIPATH_PROJECT_ID,
)
from ._utils._project_files import (
    ensure_config_file,
    get_project_config,
    validate_config,
)
from ._utils._uv_helpers import handle_uv_operations

console = ConsoleLogger()


def get_org_scoped_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    org_name, *_ = parsed.path.strip("/").split("/")

    org_scoped_url = f"{parsed.scheme}://{parsed.netloc}/{org_name}"
    return org_scoped_url


async def upload_source_files_to_project(
    project_id: str,
    config_data: dict[Any, str],
    directory: str,
    include_uv_lock: bool = True,
) -> None:
    """Upload source files to UiPath project.

    This function handles the pushing of local files to the remote project:
    - Updates existing files that have changed
    - Uploads new files that don't exist remotely
    - Deletes remote files that no longer exist locally
    - Optionally includes the UV lock file
    """
    sw_file_handler = SwFileHandler(
        project_id=project_id,
        directory=directory,
        include_uv_lock=include_uv_lock,
    )

    await sw_file_handler.upload_source_files(config_data)


@click.command()
@click.argument(
    "root", type=click.Path(exists=True, file_okay=False, dir_okay=True), default="."
)
@click.option(
    "--nolock",
    is_flag=True,
    help="Skip running uv lock and exclude uv.lock from the package",
)
@track
def push(root: str, nolock: bool) -> None:
    """Push local project files to Studio Web Project.

    This command pushes the local project files to a UiPath Studio Web project.
    It ensures that the remote project structure matches the local files by:
    - Updating existing files that have changed
    - Uploading new files
    - Deleting remote files that no longer exist locally
    - Optionally managing the UV lock file

    Args:
        root: The root directory of the project
        nolock: Whether to skip UV lock operations and exclude uv.lock from push

    Environment Variables:
        UIPATH_PROJECT_ID: Required. The ID of the UiPath Cloud project

    Example:
        $ uipath push
        $ uipath push --nolock
    """
    ensure_config_file(root)
    config = get_project_config(root)
    validate_config(config)

    if not os.getenv(UIPATH_PROJECT_ID, False):
        console.error("UIPATH_PROJECT_ID environment variable not found.")

    with console.spinner("Pushing coded UiPath project to Studio Web..."):
        try:
            if not nolock:
                handle_uv_operations(root)

            asyncio.run(
                upload_source_files_to_project(
                    os.getenv(UIPATH_PROJECT_ID),
                    config,
                    root,
                    include_uv_lock=not nolock,
                )
            )
        except Exception as e:
            console.error(f"Failed to push UiPath project: {e}")
