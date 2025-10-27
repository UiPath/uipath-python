# type: ignore
"""CLI command for pulling remote project files from UiPath StudioWeb solution.

This module provides functionality to pull remote project files from a UiPath StudioWeb solution.
It handles:
- File downloads from source_code and evals folders
- Maintaining folder structure locally
- File comparison using hashes
- Interactive confirmation for overwriting files
"""

# type: ignore
import asyncio
import os
from pathlib import Path

import click

from ..telemetry import track
from ._utils._console import ConsoleLogger
from ._utils._constants import UIPATH_PROJECT_ID
from ._utils._project_files import ProjectPullError, pull_project

console = ConsoleLogger()


@click.command()
@click.argument(
    "root",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("."),
)
@track
def pull(root: Path) -> None:
    """Pull remote project files from Studio Web Project.

    This command pulls the remote project files from a UiPath Studio Web project.
    It downloads files from the source_code and evals folders, maintaining the
    folder structure locally. Files are compared using hashes before overwriting,
    and user confirmation is required for differing files.

    Args:
        root: The root directory to pull files into

    Environment Variables:
        UIPATH_PROJECT_ID: Required. The ID of the UiPath Studio Web project

    Example:
        $ uipath pull
        $ uipath pull /path/to/project
    """
    project_id = os.getenv(UIPATH_PROJECT_ID)
    if not project_id:
        console.error("UIPATH_PROJECT_ID environment variable not found.")
        return

    download_configuration = {
        "source_code": root,
        "evals": root / "evals",
    }

    try:

        async def run_pull():
            async for update in pull_project(project_id, download_configuration):
                console.info(f"Processing: {update.file_path}")
                console.info(update.message)

        asyncio.run(run_pull())
        console.success("Project pulled successfully")
    except ProjectPullError as e:
        console.error(f"Failed to pull UiPath project: {str(e)}")
