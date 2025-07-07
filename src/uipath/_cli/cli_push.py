# type: ignore
"""CLI command for pushing local project files to UiPath StudioWeb solution.

This module provides functionality to push local project files to a UiPath StudioWeb solution.
It handles:
- File uploads and updates
- File deletions for removed local files
- Optional UV lock file management
- Project structure pushing

The push process ensures that the remote project structure matches the local files,
taking into account:
- Entry point files from uipath.json
- Project configuration from pyproject.toml
- Optional UV lock file for dependency management
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from urllib.parse import urlparse

import click
import httpx
from dotenv import load_dotenv

from .._utils._ssl_context import get_httpx_client_kwargs
from ..telemetry import track
from ._utils._common import get_env_vars
from ._utils._console import ConsoleLogger
from ._utils._constants import (
    AGENT_INITIAL_CODE_VERSION,
    AGENT_STORAGE_VERSION,
    AGENT_TARGET_RUNTIME,
    AGENT_VERSION,
)
from ._utils._project_files import (
    ensure_config_file,
    files_to_include,
    get_project_config,
    read_toml_project,
    validate_config,
)
from ._utils._studio_project import ProjectFile, ProjectFolder, ProjectStructure
from ._utils._uv_helpers import handle_uv_operations

console = ConsoleLogger()
load_dotenv(override=True)


def get_org_scoped_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    org_name, *_ = parsed.path.strip("/").split("/")

    # Construct the new scoped URL (scheme + domain + org_name)
    org_scoped_url = f"{parsed.scheme}://{parsed.netloc}/{org_name}"
    return org_scoped_url


def get_project_structure(
    project_id: str, base_url: str, token: str
) -> ProjectStructure:
    """Retrieve the project's file structure from UiPath Cloud.

    Makes an API call to fetch the complete file structure of a project,
    including all files and folders. The response is validated against
    the ProjectStructure model.
    """
    url = get_org_scoped_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure"

    with httpx.Client(**get_httpx_client_kwargs()) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return ProjectStructure.model_validate(response.json())


def collect_all_files(
    folder: ProjectFolder, files_dict: Dict[str, ProjectFile]
) -> None:
    """Recursively collect all files from a folder and its subfolders.

    Traverses the folder structure recursively and adds all files to the
    provided dictionary, using the file name as the key.
    """
    # Add files from current folder
    for file in folder.files:
        files_dict[file.name] = file

    # Recursively process subfolders
    for subfolder in folder.folders:
        collect_all_files(subfolder, files_dict)


def get_all_remote_files(structure: ProjectStructure) -> Dict[str, ProjectFile]:
    """Get all files from the project structure indexed by name.

    Creates a flat dictionary of all files in the project, including those
    in subfolders, using the file name as the key.
    """
    files: Dict[str, ProjectFile] = {}

    # Add files from root level
    for file in structure.files:
        files[file.name] = file

    # Add files from all folders recursively
    for folder in structure.folders:
        collect_all_files(folder, files)

    return files


def delete_remote_file(
    project_id: str, file_id: str, base_url: str, token: str, client: httpx.Client
) -> None:
    """Delete a file from the remote project.

    Makes an API call to delete a specific file from the UiPath Cloud project.

    Args:
        project_id: The ID of the project
        file_id: The ID of the file to delete
        base_url: The base URL for the API
        token: Authentication token
        client: HTTP client to use for the request

    Raises:
        httpx.HTTPError: If the API request fails
    """
    url = get_org_scoped_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{url}/studio_/backend/api/Project/{project_id}/FileOperations/Delete/{file_id}"

    response = client.delete(url, headers=headers)
    response.raise_for_status()


def update_agent_json(
    project_id: str,
    base_url: str,
    token: str,
    directory: str,
    client: Optional[httpx.Client] = None,
    processed_files: Optional[Set[str]] = None,
    agent_json_file: Optional[ProjectFile] = None,
) -> None:
    """Update agent.json file with metadata from uipath.json.

    This function:
    1. Downloads existing agent.json if it exists
    2. Updates metadata based on uipath.json content
    3. Increments code version
    4. Updates author from pyproject.toml
    5. Uploads updated agent.json

    Args:
        project_id: The ID of the project
        base_url: The base URL for the API
        token: Authentication token
        directory: Project root directory
        client: Optional HTTP client to use for requests
        processed_files: Optional set to track processed files

    Raises:
        httpx.HTTPError: If API requests fail
        FileNotFoundError: If required files are missing
        json.JSONDecodeError: If JSON parsing fails
    """
    url = get_org_scoped_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}

    # Read uipath.json
    with open(os.path.join(directory, "uipath.json"), "r") as f:
        uipath_config = json.load(f)

    try:
        entrypoints = [
            {"input": entry_point["input"], "output": entry_point["output"]}
            for entry_point in uipath_config["entryPoints"]
        ]
    except (FileNotFoundError, KeyError) as e:
        console.error(
            f"Unable to extract entrypoints from configuration file. Please run 'uipath init' : {str(e)}",
        )

    # Read pyproject.toml for author info
    toml_data = read_toml_project(os.path.join(directory, "pyproject.toml"))
    author = toml_data.get("authors", "").strip()

    # Initialize agent.json structure
    agent_json = {
        "version": AGENT_VERSION,
        "metadata": {
            "storageVersion": AGENT_STORAGE_VERSION,
            "targetRuntime": AGENT_TARGET_RUNTIME,
            "isConversational": False,
            "codeVersion": AGENT_INITIAL_CODE_VERSION,
            "author": author,
            "pushDate": datetime.now(timezone.utc).isoformat(),
        },
        "entryPoints": entrypoints,
        "bindings": uipath_config.get("bindings", {"version": "2.0", "resources": []}),
    }

    base_api_url = f"{url}/studio_/backend/api/Project/{project_id}/FileOperations"
    if agent_json_file:
        # Download existing agent.json
        file_url = f"{base_api_url}/File/{agent_json_file.id}"
        response = (
            client.get(file_url, headers=headers)
            if client
            else httpx.get(file_url, headers=headers)
        )
        response.raise_for_status()

        try:
            existing_agent = response.json()
            # Get current version and increment patch version
            version_parts = existing_agent["metadata"]["codeVersion"].split(".")
            if len(version_parts) >= 3:
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                agent_json["metadata"]["codeVersion"] = ".".join(version_parts)
            else:
                # If version format is invalid, start from initial version + 1
                agent_json["metadata"]["codeVersion"] = (
                    AGENT_INITIAL_CODE_VERSION[:-1] + "1"
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            console.warning(
                "Could not parse existing agent.json, using default version"
            )

    # Upload updated agent.json
    files_data = {"file": ("agent.json", json.dumps(agent_json), "application/json")}

    # if agent.json already exists update it, otherwise upload it
    if agent_json_file:
        url = f"{base_api_url}/File/{agent_json_file.id}"
        response = (
            client.put(url, files=files_data, headers=headers)
            if client
            else httpx.put(url, files=files_data, headers=headers)
        )
    else:
        url = f"{base_api_url}/File"
        response = (
            client.post(url, files=files_data, headers=headers)
            if client
            else httpx.post(url, files=files_data, headers=headers)
        )

    response.raise_for_status()
    console.success(f"Updated {click.style('agent.json', fg='cyan')}")

    # Mark agent.json as processed to prevent deletion
    if processed_files is not None:
        processed_files.add("agent.json")


def upload_source_files_to_project(
    project_id: str,
    config_data: dict[Any, str],
    directory: str,
    base_url: str,
    token: str,
    include_uv_lock: bool = True,
) -> None:
    """Upload source files to UiPath project.

    This function handles the pushing of local files to the remote project:
    - Updates existing files that have changed
    - Uploads new files that don't exist remotely
    - Deletes remote files that no longer exist locally
    - Optionally includes the UV lock file
    """
    files = [
        file.file_path.replace("./", "", 1)
        for file in files_to_include(config_data, directory)
    ]
    optional_files = ["pyproject.toml"]

    for file in optional_files:
        file_path = os.path.join(directory, file)
        if os.path.exists(file_path):
            files.append(file)
    if include_uv_lock:
        files.append("uv.lock")

    url = get_org_scoped_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    base_api_url = f"{url}/studio_/backend/api/Project/{project_id}/FileOperations"

    # get existing project structure
    try:
        structure = get_project_structure(project_id, base_url, token)
        remote_files = get_all_remote_files(structure)
    except Exception as e:
        console.error(f"Failed to get project structure: {str(e)}")
        raise

    # keep track of processed files to identify which ones to delete later
    processed_files: Set[str] = set()

    with httpx.Client(**get_httpx_client_kwargs()) as client:
        # Update agent.json first
        try:
            update_agent_json(
                project_id,
                base_url,
                token,
                directory,
                client,
                processed_files,
                remote_files.get("agent.json", None),
            )
        except Exception as e:
            console.error(f"Failed to update agent.json: {str(e)}")
            raise

        # Continue with rest of files
        for file_path in files:
            try:
                abs_path = os.path.abspath(os.path.join(directory, file_path))
                if not os.path.exists(abs_path):
                    console.warning(
                        f"File not found: {click.style(abs_path, fg='cyan')}"
                    )
                    continue

                file_name = os.path.basename(file_path)
                remote_file = remote_files.get(file_name)
                processed_files.add(file_name)

                with open(abs_path, "rb") as f:
                    files_data = {"file": (file_name, f, "application/octet-stream")}

                    if remote_file:
                        # File exists, use PUT to update
                        url = f"{base_api_url}/File/{remote_file.id}"
                        response = client.put(url, files=files_data, headers=headers)
                        action = "Updated"
                    else:
                        # File doesn't exist, use POST to create
                        url = f"{base_api_url}/File"
                        response = client.post(url, files=files_data, headers=headers)
                        action = "Uploaded"

                    response.raise_for_status()
                    console.success(f"{action} {click.style(file_path, fg='cyan')}")

            except Exception as e:
                console.error(
                    f"Failed to upload {click.style(file_path, fg='cyan')}: {str(e)}"
                )
                raise

        # Delete files that no longer exist locally
        if remote_files:
            for file_name, remote_file in remote_files.items():
                if file_name not in processed_files:
                    try:
                        delete_remote_file(
                            project_id, remote_file.id, base_url, token, client
                        )
                        console.success(
                            f"Deleted remote file {click.style(file_name, fg='cyan')}"
                        )
                    except Exception as e:
                        console.error(
                            f"Failed to delete remote file {click.style(file_name, fg='cyan')}: {str(e)}"
                        )
                        raise


@click.command()
@click.argument("root", type=str, default="./")
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

    if not os.getenv("UIPATH_PROJECT_ID", False):
        console.error("UIPATH_PROJECT_ID environment variable not found.")
    [base_url, token] = get_env_vars()

    with console.spinner("Pushing coded UiPath project to Studio Web..."):
        try:
            # Handle uv operations before packaging, unless nolock is specified
            if not nolock:
                handle_uv_operations(root)

            upload_source_files_to_project(
                os.getenv("UIPATH_PROJECT_ID"),
                config,
                root,
                base_url,
                token,
                include_uv_lock=not nolock,
            )
        except Exception:
            console.error("Failed to push UiPath project")
