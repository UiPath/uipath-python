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
import hashlib
import json
import os
from pathlib import Path
from typing import Dict

import click

from ..telemetry import track
from ._utils._console import ConsoleLogger
from ._utils._constants import UIPATH_PROJECT_ID
from ._utils._studio_project import (
    ProjectFile,
    ProjectFolder,
    StudioClient,
    get_folder_by_name,
)

console = ConsoleLogger()


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


async def download_folder_files(
    studio_client: StudioClient,
    folder: ProjectFolder,
    base_path: Path,
) -> None:
    """Download files from a folder recursively.

    Args:
        studio_client: Studio client
        folder: The folder to download files from
        base_path: Base path for local file storage
    """
    files_dict: Dict[str, ProjectFile] = {}
    collect_files_from_folder(folder, "", files_dict)
    for file_path, remote_file in files_dict.items():
        local_path = base_path / file_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Download remote file
        response = await studio_client.download_file_async(remote_file.id)
        remote_content = response.read().decode("utf-8")
        remote_hash = compute_normalized_hash(remote_content)

        if os.path.exists(local_path):
            # Read and hash local file
            with open(local_path, "r", encoding="utf-8") as f:
                local_content = f.read()
                local_hash = compute_normalized_hash(local_content)

            # Compare hashes
            if local_hash != remote_hash:
                styled_path = click.style(str(file_path), fg="cyan")
                console.warning(f"File {styled_path}" + " differs from remote version.")
                response = click.prompt("Do you want to overwrite it? (y/n)", type=str)
                if response.lower() == "y":
                    with open(local_path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(remote_content)
                    console.success(f"Updated {click.style(str(file_path), fg='cyan')}")
                else:
                    console.info(f"Skipped {click.style(str(file_path), fg='cyan')}")
            else:
                console.info(
                    f"File {click.style(str(file_path), fg='cyan')} is up to date"
                )
        else:
            # File doesn't exist locally, create it
            with open(local_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(remote_content)
            console.success(f"Downloaded {click.style(str(file_path), fg='cyan')}")


async def pull_project(project_id: str, download_configuration: dict[str, Path]):
    studio_client = StudioClient(project_id)

    with console.spinner("Pulling UiPath project files..."):
        try:
            structure = await studio_client.get_project_structure_async()
            for source_key, destination in download_configuration.items():
                source_folder = get_folder_by_name(structure, source_key)
                if source_folder:
                    await download_folder_files(
                        studio_client,
                        source_folder,
                        destination,
                    )
                else:
                    console.warning(f"No {source_key} folder found in remote project")

        except Exception as e:
            console.error(f"Failed to pull UiPath project: {str(e)}")


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
    if not (project_id := os.getenv(UIPATH_PROJECT_ID, False)):
        console.error("UIPATH_PROJECT_ID environment variable not found.")

    default_download_configuration = {
        "source_code": root,
        "evals": root / "evals",
    }
    asyncio.run(pull_project(project_id, default_download_configuration))
