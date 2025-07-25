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
import hashlib
import json
import os
from typing import Dict, Set

import click
import httpx
from dotenv import load_dotenv

from .._utils._ssl_context import get_httpx_client_kwargs
from ..telemetry import track
from ._utils._common import get_env_vars, get_org_scoped_url
from ._utils._console import ConsoleLogger
from ._utils._studio_project import (
    ProjectFile,
    ProjectFolder,
    download_file,
    get_folder_by_name,
    get_project_structure,
)

console = ConsoleLogger()
load_dotenv(override=True)


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


def download_folder_files(
    folder: ProjectFolder,
    base_path: str,
    base_url: str,
    token: str,
    client: httpx.Client,
    processed_files: Set[str],
) -> None:
    """Download files from a folder recursively.

    Args:
        folder: The folder to download files from
        base_path: Base path for local file storage
        base_url: Base URL for API requests
        token: Authentication token
        client: HTTP client
        processed_files: Set to track processed files
    """
    files_dict: Dict[str, ProjectFile] = {}
    collect_files_from_folder(folder, "", files_dict)

    for file_path, remote_file in files_dict.items():
        local_path = os.path.join(base_path, file_path)
        local_dir = os.path.dirname(local_path)

        # Create directory if it doesn't exist
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)

        # Download remote file
        response = download_file(base_url, remote_file.id, client, token)
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
                response = click.prompt("Do you want to override it? (y/n)", type=str)
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

        processed_files.add(file_path)


@click.command()
@click.argument(
    "root", type=click.Path(exists=True, file_okay=False, dir_okay=True), default="."
)
@track
def pull(root: str) -> None:
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
    if not os.getenv("UIPATH_PROJECT_ID", False):
        console.error("UIPATH_PROJECT_ID environment variable not found.")

    [base_url, token] = get_env_vars()
    base_api_url = f"{get_org_scoped_url(base_url)}/studio_/backend/api/Project/{os.getenv('UIPATH_PROJECT_ID')}/FileOperations"

    with console.spinner("Pulling UiPath project files..."):
        try:
            with httpx.Client(**get_httpx_client_kwargs()) as client:
                # Get project structure
                structure = get_project_structure(
                    os.getenv("UIPATH_PROJECT_ID"),  # type: ignore
                    get_org_scoped_url(base_url),
                    token,
                    client,
                )

                processed_files: Set[str] = set()

                # Process source_code folder
                source_code_folder = get_folder_by_name(structure, "source_code")
                if source_code_folder:
                    download_folder_files(
                        source_code_folder,
                        root,
                        base_api_url,
                        token,
                        client,
                        processed_files,
                    )
                else:
                    console.warning("No source_code folder found in remote project")

                # Process evals folder
                evals_folder = get_folder_by_name(structure, "evals")
                if evals_folder:
                    evals_path = os.path.join(root, "evals")
                    download_folder_files(
                        evals_folder,
                        evals_path,
                        base_api_url,
                        token,
                        client,
                        processed_files,
                    )
                else:
                    console.warning("No evals folder found in remote project")

        except Exception as e:
            console.error(f"Failed to pull UiPath project: {str(e)}")
