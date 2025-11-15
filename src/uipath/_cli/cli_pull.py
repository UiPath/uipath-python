# type: ignore
"""CLI command for pulling remote project files from UiPath StudioWeb solution."""

# type: ignore
import asyncio
from pathlib import Path

import click

from .._config import UiPathConfig
from ._utils._console import ConsoleLogger
from ._utils._project_files import (
    InteractiveConflictHandler,
    ProjectPullError,
    pull_project,
)

console = ConsoleLogger()


@click.command()
@click.argument(
    "root",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("."),
)
def pull(root: Path) -> None:
    """Pull remote project files from Studio Web Project.

    This command pulls the remote project files from a UiPath Studio Web project.

    Args:
        root: The root directory to pull files into

    Environment Variables:
        UIPATH_PROJECT_ID: Required. The ID of the UiPath Studio Web project

    Example:
        $ uipath pull
        $ uipath pull /path/to/project
    """
    project_id = UiPathConfig.project_id
    if not project_id:
        console.error("UIPATH_PROJECT_ID environment variable not found.")

    download_configuration = {
        None: root,
    }

    # Create interactive conflict handler for user confirmation
    conflict_handler = InteractiveConflictHandler(operation="pull")
    console.log("Pulling UiPath project from Studio Web...")

    try:

        async def run_pull():
            async for update in pull_project(
                project_id, download_configuration, conflict_handler
            ):
                console.info(f"Processing: {update.file_path}")
                console.info(update.message)

        asyncio.run(run_pull())
        console.success("Project pulled successfully")
    except ProjectPullError as e:
        console.error(f"Failed to pull UiPath project: {str(e)}")
