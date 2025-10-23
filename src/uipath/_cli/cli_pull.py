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
from typing import Dict, Set

import click

from ..telemetry import track
from ._utils._console import ConsoleLogger
from ._utils._constants import UIPATH_PROJECT_ID
from ._utils._studio_project import (
    ProjectFile,
    ProjectFolder,
    StudioClient,
    get_folder_by_name,
    get_subfolder_by_name,
)
from ._utils._project_files import ProjectPullError, pull_project

console = ConsoleLogger()


def has_version_property(content: str) -> bool:
    """Check if a JSON file has a version property, indicating it's a new coded-evals file.

    Args:
        content: File content to check

    Returns:
        bool: True if the file has a version property, False otherwise
    """
    try:
        data = json.loads(content)
        return "version" in data
    except json.JSONDecodeError:
        return False


def compute_normalized_hash(content: str) -> str:
    """Compute hash of normalized content.

    Args:
        content: Content to hash

    Returns:
        str: SHA256 hash of the normalized content
    """
    try:
        # Try to parse as JSON to handle formatting
        json_content = json.loads(content)
        normalized = json.dumps(json_content, indent=2)
    except json.JSONDecodeError:
        # Not JSON, normalize line endings
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def collect_files_from_folder(
    folder: ProjectFolder, base_path: str, files_dict: Dict[str, ProjectFile]
) -> None:
    """Recursively collect all files from a folder and its subfolders.

    Args:
        folder: The folder to collect files from
        base_path: Base path for file paths
        files_dict: Dictionary to store collected files
    """
    # Add files from current folder
    for file in folder.files:
        file_path = os.path.join(base_path, file.name)
        files_dict[file_path] = file

    # Recursively process subfolders
    for subfolder in folder.folders:
        subfolder_path = os.path.join(base_path, subfolder.name)
        collect_files_from_folder(subfolder, subfolder_path, files_dict)
class InteractiveConflictHandler:
    """Handler that prompts user for each conflict."""

    def __init__(self, console: ConsoleLogger):
        self.console = console

    def should_overwrite(
        self, file_path: str, local_hash: str, remote_hash: str
    ) -> bool:
        self.console.warning(f" File {file_path} differs from remote version.")
        response = click.confirm("Do you want to overwrite it?", default=False)
        return response


async def download_coded_evals_files(
    studio_client: StudioClient,
    coded_evals_folder: ProjectFolder,
    root: str,
    processed_files: Set[str],
) -> None:
    """Download coded-evals files and map them to local evals structure.

    Args:
        studio_client: Studio client
        coded_evals_folder: The coded-evals folder from remote
        root: Root path for local storage
        processed_files: Set to track processed files
    """
    # Map coded-evals/evaluators → local evals/evaluators
    evaluators_subfolder = get_subfolder_by_name(coded_evals_folder, "evaluators")
    if evaluators_subfolder:
        local_evaluators_path = os.path.join(root, "evals", "evaluators")
        await download_folder_files(
            studio_client,
            evaluators_subfolder,
            local_evaluators_path,
            processed_files,
        )

    # Map coded-evals/eval-sets → local evals/eval-sets
    eval_sets_subfolder = get_subfolder_by_name(coded_evals_folder, "eval-sets")
    if eval_sets_subfolder:
        local_eval_sets_path = os.path.join(root, "evals", "eval-sets")
        await download_folder_files(
            studio_client,
            eval_sets_subfolder,
            local_eval_sets_path,
            processed_files,
        )


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

    default_download_configuration = {
        "source_code": root,
        "evals": root / "evals",
    }

    async def pull_with_updates():
        try:
            structure = asyncio.run(studio_client.get_project_structure_async())

            processed_files: Set[str] = set()

            # Process source_code folder
            source_code_folder = get_folder_by_name(structure, "source_code")
            if source_code_folder:
                asyncio.run(
                    download_folder_files(
                        studio_client,
                        source_code_folder,
                        root,
                        processed_files,
                    )
                )
            else:
                console.warning("No source_code folder found in remote project")

            # Process evaluation folders - check for coded-evals first
            coded_evals_folder = get_folder_by_name(structure, "coded-evals")

            if coded_evals_folder:
                # New structure: coded-evals folder exists, use it and skip legacy evals
                console.info(
                    "Found coded-evals folder, downloading to local evals structure"
                )
                asyncio.run(
                    download_coded_evals_files(
                        studio_client,
                        coded_evals_folder,
                        root,
                        processed_files,
                    )
                )
            else:
                # Fallback to legacy evals folder
                evals_folder = get_folder_by_name(structure, "evals")
                if evals_folder:
                    console.info(
                        "Found legacy evals folder, downloading to local evals structure"
                    )
                    evals_path = os.path.join(root, "evals")
                    asyncio.run(
                        download_folder_files(
                            studio_client,
                            evals_folder,
                            evals_path,
                            processed_files,
                        )
                    )
                else:
                    console.warning("No evaluation folders found in remote project")

        except Exception as e:
            console.error(f"Failed to pull UiPath project: {str(e)}")
