"""Studio Web File Handler for managing file operations in UiPath projects."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

import click

from .._utils._console import ConsoleLogger
from .._utils._constants import (
    AGENT_INITIAL_CODE_VERSION,
    AGENT_STORAGE_VERSION,
    AGENT_TARGET_RUNTIME,
    AGENT_VERSION,
)
from .._utils._project_files import (  # type: ignore
    FileInfo,
    files_to_include,
    read_toml_project,
)
from .._utils._studio_project import (
    AddedResource,
    ModifiedResource,
    ProjectFile,
    ProjectFolder,
    ProjectStructure,
    StructuralMigration,
    StudioClient,
)


class SwFileHandler:
    """Handler for Studio Web file operations.

    This class encapsulates all file operations for UiPath Studio Web projects,
    including uploading, updating, deleting, and managing project structure.

    Attributes:
        directory: Local project directory
        include_uv_lock: Whether to include uv.lock file
        console: Console logger instance
    """

    def __init__(
        self,
        project_id: str,
        directory: str,
        include_uv_lock: bool = True,
    ) -> None:
        """Initialize the SwFileHandler.

        Args:
            project_id: The ID of the UiPath project
            directory: Local project directory
            include_uv_lock: Whether to include uv.lock file
        """
        self.directory = directory
        self.include_uv_lock = include_uv_lock
        self.console = ConsoleLogger()
        self._studio_client = StudioClient(project_id)
        self._project_structure: Optional[ProjectStructure] = None

    def _get_folder_by_name(
        self, structure: ProjectStructure, folder_name: str
    ) -> Optional[ProjectFolder]:
        """Get a folder from the project structure by name.

        Args:
            folder_name: Name of the folder to find

        Returns:
            Optional[ProjectFolder]: The found folder or None
        """
        for folder in structure.folders:
            if folder.name == folder_name:
                return folder
        return None

    def collect_all_files(
        self,
        folder: ProjectFolder,
        files_dict: Dict[str, ProjectFile],
        current_path: str = "",
    ) -> None:
        """Recursively collect all files from a folder with computed paths.

        Args:
            folder: The folder to traverse
            files_dict: Dictionary to store files (indexed by name)
            current_path: The current path prefix for files in this folder
        """
        # Add files from current folder
        for file in folder.files:
            file_path = f"{current_path}/{file.name}" if current_path else file.name
            files_dict[file_path] = file

        # Recursively process subfolders
        for subfolder in folder.folders:
            subfolder_path = (
                f"{current_path}/{subfolder.name}" if current_path else subfolder.name
            )
            self.collect_all_files(subfolder, files_dict, subfolder_path)

    def _get_remote_files(
        self,
        structure: ProjectStructure,
        source_code_folder: Optional[ProjectFolder] = None,
    ) -> tuple[Dict[str, ProjectFile], Dict[str, ProjectFile]]:
        """Get all files from the project structure indexed by name.

        Args:
            structure: The project structure
            source_code_folder: Optional source_code folder to collect files from

        Returns:
            Tuple of (root_files, source_code_files) dictionaries with file paths as keys
        """
        root_files: Dict[str, ProjectFile] = {}
        source_code_files: Dict[str, ProjectFile] = {}

        # Add files from root level
        for file in structure.files:
            root_files[file.name] = file

        # Add files from source_code folder if it exists
        if source_code_folder:
            self.collect_all_files(source_code_folder, source_code_files)

        return root_files, source_code_files

    async def _process_file_uploads(
        self,
        local_files: list[FileInfo],
        source_code_files: Dict[str, ProjectFile],
    ) -> None:
        """Process all file uploads to the source_code folder.

        Args:
            local_files: List of files to upload
            source_code_files: Dictionary of existing remote files

        Returns:
            Set of processed file names

        Raises:
            Exception: If any file upload fails
        """
        structural_migration = StructuralMigration(
            deleted_resources=[], added_resources=[], modified_resources=[]
        )
        processed_source_files: Set[str] = set()

        for local_file in local_files:
            if not os.path.exists(local_file.file_path):
                self.console.warning(
                    f"File not found: {click.style(local_file.file_path, fg='cyan')}"
                )
                continue

            # Skip agent.json as it's handled separately
            if local_file.file_name == "agent.json":
                continue

            remote_file = source_code_files.get(
                local_file.relative_path.replace("\\", "/"), None
            )
            if remote_file:
                processed_source_files.add(remote_file.id)
                structural_migration.modified_resources.append(
                    ModifiedResource(
                        id=remote_file.id, content_file_path=local_file.file_path
                    )
                )
                self.console.info(
                    f"Updating {click.style(local_file.file_name, fg='yellow')}"
                )
            else:
                parent_path = os.path.dirname(local_file.relative_path)
                structural_migration.added_resources.append(
                    AddedResource(
                        content_file_path=local_file.file_path,
                        parent_path=f"source_code/{parent_path}"
                        if parent_path != ""
                        else "source_code",
                    )
                )
                self.console.info(
                    f"Uploading {click.style(local_file.file_name, fg='cyan')}"
                )

        # identify and add deleted files
        structural_migration.deleted_resources.extend(
            self._collect_deleted_files(source_code_files, processed_source_files)
        )
        await self._studio_client.perform_structural_migration_async(
            structural_migration
        )

        # Clean up empty folders after migration
        await self._cleanup_empty_folders()

    def _collect_deleted_files(
        self,
        source_code_files: Dict[str, ProjectFile],
        processed_source_file_paths: Set[str],
    ) -> set[str]:
        """Delete remote files that no longer exist locally.

        Args:
            source_code_files: Dictionary of existing remote files
            processed_source_file_paths: Set of files that were processed

        Raises:
            Exception: If any file deletion fails
        """
        if not source_code_files:
            return set()

        deleted_files: Set[str] = set()
        for _, remote_file in source_code_files.items():
            if remote_file.id not in processed_source_file_paths:
                deleted_files.add(remote_file.id)
                self.console.info(
                    f"Deleting {click.style(remote_file.name, fg='bright_red')}"
                )

        return deleted_files

    async def _cleanup_empty_folders(self) -> None:
        """Clean up empty folders in the source_code directory after structural migration.

        This method:
        1. Gets the current project structure
        2. Recursively checks for empty folders within source_code
        3. Deletes any empty folders found
        """
        try:
            structure = await self._studio_client.get_project_structure_async()
            source_code_folder = self._get_folder_by_name(structure, "source_code")

            if not source_code_folder:
                return

            # Collect all empty folders (bottom-up to avoid parent-child deletion conflicts)
            empty_folder_ids = self._collect_empty_folders(source_code_folder)

            for folder_info in empty_folder_ids:
                try:
                    await self._studio_client.delete_item_async(folder_info["id"])
                    self.console.info(
                        f"Deleted empty folder {click.style(folder_info['name'], fg='bright_red')}"
                    )
                except Exception as e:
                    self.console.warning(
                        f"Failed to delete empty folder {folder_info['name']}: {str(e)}"
                    )

        except Exception as e:
            self.console.warning(f"Failed to cleanup empty folders: {str(e)}")

    def _collect_empty_folders(self, folder: ProjectFolder) -> list[dict[str, str]]:
        """Recursively collect IDs and names of empty folders.

        Args:
            folder: The folder to check for empty subfolders

        Returns:
            List of dictionaries containing folder ID and name for empty folders
        """
        empty_folders: list[dict[str, str]] = []

        # Process subfolders first
        for subfolder in folder.folders:
            empty_subfolders = self._collect_empty_folders(subfolder)
            empty_folders.extend(empty_subfolders)

            # Check if the current folder is empty after processing its children
            if self._is_folder_empty(subfolder):
                empty_folders.append({"id": subfolder.id, "name": subfolder.name})

        return empty_folders

    def _is_folder_empty(self, folder: ProjectFolder) -> bool:
        """Check if a folder is empty (no files and no non-empty subfolders).

        Args:
            folder: The folder to check

        Returns:
            True if the folder is empty, False otherwise
        """
        if folder.files:
            return False

        if not folder.folders:
            return True

        # If folder has subfolders, check if all subfolders are empty
        for subfolder in folder.folders:
            if not self._is_folder_empty(subfolder):
                return False

        return True

    async def _update_agent_json(
        self,
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
            agent_json_file: Optional existing agent.json file

        Raises:
            httpx.HTTPError: If API requests fail
            FileNotFoundError: If required files are missing
            json.JSONDecodeError: If JSON parsing fails
        """

        def get_author_from_token_or_toml() -> str:
            import jwt

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
                    decoded_token = jwt.decode(
                        token, options={"verify_signature": False}
                    )
                    preferred_username = decoded_token.get("preferred_username")
                    if preferred_username:
                        return preferred_username
                except Exception:
                    # If JWT decoding fails, fall back to toml
                    pass

            toml_data = read_toml_project(os.path.join(directory, "pyproject.toml"))

            return toml_data.get("authors", "").strip()

        # Read uipath.json
        directory = os.getcwd()
        with open(os.path.join(directory, "uipath.json"), "r") as f:
            uipath_config = json.load(f)

        try:
            entrypoints = [
                {"input": entry_point["input"], "output": entry_point["output"]}
                for entry_point in uipath_config["entryPoints"]
            ]
        except (FileNotFoundError, KeyError) as e:
            self.console.error(
                f"Unable to extract entrypoints from configuration file. Please run 'uipath init' : {str(e)}",
            )

        author = get_author_from_token_or_toml()

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
            "bindings": uipath_config.get(
                "bindings", {"version": "2.0", "resources": []}
            ),
        }

        if agent_json_file:
            # Download existing agent.json
            existing_agent_json = (
                await self._studio_client.download_file_async(agent_json_file.id)
            ).json()

            try:
                # Get current version and increment patch version
                version_parts = existing_agent_json["metadata"]["codeVersion"].split(
                    "."
                )
                if len(version_parts) >= 3:
                    version_parts[-1] = str(int(version_parts[-1]) + 1)
                    agent_json["metadata"]["codeVersion"] = ".".join(version_parts)
                else:
                    # If version format is invalid, start from initial version + 1
                    agent_json["metadata"]["codeVersion"] = (
                        AGENT_INITIAL_CODE_VERSION[:-1] + "1"
                    )
            except (json.JSONDecodeError, KeyError, ValueError):
                self.console.warning(
                    "Could not parse existing agent.json, using default version"
                )
        file, action = await self._studio_client.upload_file_async(
            file_content=json.dumps(agent_json),
            file_name="agent.json",
            remote_file=agent_json_file,
        )
        self.console.success(f"{action} {click.style('agent.json', fg='cyan')}")

    async def upload_source_files(self, config_data: dict[str, Any]) -> None:
        """Main method to upload source files to the UiPath project.

        - Gets project structure
        - Creates source_code folder if needed
        - Uploads/updates files
        - Deletes removed files

        Args:
            config_data: Project configuration data

        Returns:
            Dict[str, ProjectFileExtended]: Root level files for agent.json handling

        Raises:
            Exception: If any step in the process fails
        """
        structure = await self._studio_client.get_project_structure_async()
        source_code_folder = self._get_folder_by_name(structure, "source_code")
        root_files, source_code_files = self._get_remote_files(
            structure, source_code_folder
        )

        # Create source_code folder if it doesn't exist
        if not source_code_folder:
            await self._studio_client.create_folder_async("source_code")

            self.console.success(
                f"Created {click.style('source_code', fg='cyan')} folder"
            )
            source_code_files = {}

        # Get files to upload and process them
        files = files_to_include(
            config_data,
            self.directory,
            self.include_uv_lock,
            directories_to_ignore=["evals"],
        )
        await self._process_file_uploads(files, source_code_files)

        await self._update_agent_json(
            root_files.get("agent.json", None),
        )
