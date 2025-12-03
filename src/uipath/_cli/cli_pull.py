"""CLI command for pulling remote project files from UiPath StudioWeb solution."""

import asyncio
from pathlib import Path

import click

from uipath.platform.common import UiPathConfig

from ._utils._common import ensure_coded_agent_project, may_override_files
from ._utils._console import ConsoleLogger
from ._utils._project_files import (
    ProjectPullError,
    pull_project,
)
from ._utils._studio_project import StudioClient

console = ConsoleLogger()


@click.command()
@click.argument(
    "root",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("."),
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Automatically overwrite local files without prompts",
)
def pull(root: Path, overwrite: bool) -> None:
    """Pull remote project files from Studio Web.

    This command pulls the remote project files from a UiPath Studio Web project.

    Args:
        root: The root directory to pull files into
        overwrite: Whether to automatically overwrite local files without prompts

    Environment Variables:
        UIPATH_PROJECT_ID: Required. The ID of the UiPath Studio Web project

    Example:
        $ uipath pull
        $ uipath pull /path/to/project
        $ uipath pull --overwrite
    """
    project_id = UiPathConfig.project_id
    if not project_id:
        console.error("UIPATH_PROJECT_ID environment variable not found.")
        return

    studio_client = StudioClient(project_id=project_id)

    asyncio.run(ensure_coded_agent_project(studio_client))

    if not overwrite:
        may_override = asyncio.run(may_override_files(studio_client, "local"))
        if not may_override:
            console.info("Operation aborted.")
            return

    download_configuration: dict[str | None, Path] = {
        None: root,
    }

    console.log("Pulling UiPath project from Studio Web...")

    try:

        async def run_pull():
            async for update in pull_project(
                project_id, download_configuration, studio_client
            ):
                console.info(f"Processing: {update.file_path}")
                console.info(update.message)

        asyncio.run(run_pull())
        console.success("Project pulled successfully")
    except ProjectPullError as e:
        console.error(f"Failed to pull UiPath project: {str(e)}")
