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
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import urlparse

import click
import httpx
import jwt
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


def get_author_from_token_or_toml(directory: str) -> str:
    """Extract preferred_username from JWT token or fall back to pyproject.toml author.

    Args:
        directory: Project directory containing pyproject.toml

    Returns:
        str: Author name from JWT preferred_username or pyproject.toml authors field
    """
    # Try to get author from JWT token first
    token = os.getenv("UIPATH_ACCESS_TOKEN")
    if token:
        try:
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            preferred_username = decoded_token.get("preferred_username")
            if preferred_username:
                return preferred_username
        except Exception:
            # If JWT decoding fails, fall back to toml
            pass

    toml_data = read_toml_project(os.path.join(directory, "pyproject.toml"))
    return toml_data.get("authors", "").strip()


def get_org_scoped_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    org_name, *_ = parsed.path.strip("/").split("/")

    # Construct the new scoped URL (scheme + domain + org_name)
    org_scoped_url = f"{parsed.scheme}://{parsed.netloc}/{org_name}"
    return org_scoped_url


def get_project_structure(
    project_id: str,
    base_url: str,
    token: str,
    client: httpx.Client,
) -> ProjectStructure:
    """Retrieve the project's file structure from UiPath Cloud.

    Makes an API call to fetch the complete file structure of a project,
    including all files and folders. The response is validated against
    the ProjectStructure model.

    Args:
        project_id: The ID of the project
        base_url: The base URL for the API
        token: Authentication token
        client: HTTP client to use for requests

    Returns:
        ProjectStructure: The complete project structure

    Raises:
        httpx.HTTPError: If the API request fails
    """
    url = get_org_scoped_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure"

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


def get_folder_by_name(
    structure: ProjectStructure, folder_name: str
) -> Optional[ProjectFolder]:
    """Get a folder from the project structure by name.

    Args:
        structure: The project structure
        folder_name: Name of the folder to find

    Returns:
        Optional[ProjectFolder]: The found folder or None
    """
    for folder in structure.folders:
        if folder.name == folder_name:
            return folder
    return None


def get_all_remote_files(
    structure: ProjectStructure, source_code_folder: Optional[ProjectFolder] = None
) -> Tuple[Dict[str, ProjectFile], Dict[str, ProjectFile]]:
    """Get all files from the project structure indexed by name.

    Creates two flat dictionaries of files in the project:
    1. Root level files
    2. Files in the source_code folder (if exists)

    Args:
        structure: The project structure
        source_code_folder: Optional source_code folder to collect files from

    Returns:
        Tuple[Dict[str, ProjectFile], Dict[str, ProjectFile]]:
            (root_files, source_code_files)
    """
    root_files: Dict[str, ProjectFile] = {}
    source_code_files: Dict[str, ProjectFile] = {}

    # Add files from root level
    for file in structure.files:
        root_files[file.name] = file

    # Add files from source_code folder if it exists
    if source_code_folder:
        collect_all_files(source_code_folder, source_code_files)

    return root_files, source_code_files


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
    client: httpx.Client,
    processed_files: Optional[Set[str]] = None,
    agent_json_file: Optional[ProjectFile] = None,
) -> None:
    """Update agent.json file with metadata from uipath.json.

    This function:
    1. Downloads existing agent.json if it exists
    2. Updates metadata based on uipath.json content
    3. Increments code version
    4. Updates author from JWT or pyproject.toml
    5. Uploads updated agent.json

    Args:
        project_id: The ID of the project
        base_url: The base URL for the API
        token: Authentication token
        directory: Project root directory
        client: HTTP client to use for requests
        processed_files: Optional set to track processed files
        agent_json_file: Optional existing agent.json file

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

    author = get_author_from_token_or_toml(directory)

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
        response = client.get(file_url, headers=headers)
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
        response = client.put(url, files=files_data, headers=headers)
    else:
        url = f"{base_api_url}/File"
        response = client.post(url, files=files_data, headers=headers)

    response.raise_for_status()
    console.success(f"Updated {click.style('agent.json', fg='cyan')}")

    # Mark agent.json as processed to prevent deletion
    if processed_files is not None:
        processed_files.add("agent.json")


def create_project_folder(
    project_id: str,
    folder_name: str,
    base_url: str,
    token: str,
    client: httpx.Client,
) -> ProjectFolder:
    """Create a new folder in the project.

    Args:
        project_id: The ID of the project
        folder_name: Name of the folder to create
        base_url: The base URL for the API
        token: Authentication token
        client: HTTP client to use for requests

    Returns:
        ProjectFolder: The created folder object

    Raises:
        httpx.HTTPError: If the API request fails
    """
    url = get_org_scoped_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{url}/studio_/backend/api/Project/{project_id}/FileOperations/Folder"

    data = {"name": folder_name}
    response = client.post(url, json=data, headers=headers)
    response.raise_for_status()
    return ProjectFolder(name="source_code", id=response.content.decode("utf-8"))


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
    if include_uv_lock:
        files.append("uv.lock")

    url = get_org_scoped_url(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    base_api_url = f"{url}/studio_/backend/api/Project/{project_id}/FileOperations"

    with httpx.Client(**get_httpx_client_kwargs()) as client:
        # get existing project structure
        try:
            structure = get_project_structure(project_id, base_url, token, client)
            source_code_folder = get_folder_by_name(structure, "source_code")
            root_files, source_code_files = get_all_remote_files(
                structure, source_code_folder
            )
        except Exception as e:
            console.error(f"Failed to get project structure: {str(e)}")
            raise

        # keep track of processed files to identify which ones to delete later
        processed_root_files: Set[str] = set()
        processed_source_files: Set[str] = set()

        # Create source_code folder if it doesn't exist
        if not source_code_folder:
            try:
                source_code_folder = create_project_folder(
                    project_id, "source_code", base_url, token, client
                )
                console.success(
                    f"Created {click.style('source_code', fg='cyan')} folder"
                )
                source_code_files = {}  # Initialize empty dict for new folder
            except httpx.HTTPStatusError as http_err:
                if http_err.response.status_code == 423:
                    console.error(
                        "Resource is locked. Unable to create 'source_code' folder."
                    )
                raise

            except Exception as e:
                console.error(f"Failed to create 'source_code' folder: {str(e)}")
                raise

        # Update agent.json first at root level
        try:
            update_agent_json(
                project_id,
                base_url,
                token,
                directory,
                client,
                processed_root_files,
                root_files.get("agent.json", None),
            )
        except Exception as e:
            console.error(f"Failed to update agent.json: {str(e)}")
            raise

        # Continue with rest of files in source_code folder
        for file_path in files:
            try:
                abs_path = os.path.abspath(os.path.join(directory, file_path))
                if not os.path.exists(abs_path):
                    console.warning(
                        f"File not found: {click.style(abs_path, fg='cyan')}"
                    )
                    continue

                file_name = os.path.basename(file_path)

                # Skip agent.json as it's already handled
                if file_name == "agent.json":
                    continue

                remote_file = source_code_files.get(file_name)
                processed_source_files.add(file_name)

                with open(abs_path, "rb") as f:
                    files_data = {"file": (file_name, f, "application/octet-stream")}
                    form_data = {"parentId": source_code_folder.id}

                    if remote_file:
                        # File exists in source_code folder, use PUT to update
                        url = f"{base_api_url}/File/{remote_file.id}"
                        response = client.put(url, files=files_data, headers=headers)
                        action = "Updated"
                    else:
                        # File doesn't exist, use POST to create in source_code folder
                        url = f"{base_api_url}/File"
                        response = client.post(
                            url, files=files_data, data=form_data, headers=headers
                        )
                        action = "Uploaded"

                    response.raise_for_status()
                    console.success(f"{action} {click.style(file_path, fg='cyan')}")

            except Exception as e:
                console.error(
                    f"Failed to upload {click.style(file_path, fg='cyan')}: {str(e)}"
                )
                raise

        # Delete files that no longer exist locally
        if source_code_files:
            for file_name, remote_file in source_code_files.items():
                if file_name not in processed_source_files:
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
