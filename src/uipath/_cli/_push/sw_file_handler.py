"""Studio Web File Handler for managing file operations in UiPath projects."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional, Set

import click

from ..._config import UiPathConfig
from ...models.exceptions import EnrichedException
from .._utils._common import get_claim_from_token
from .._utils._console import ConsoleLogger
from .._utils._constants import (
    AGENT_INITIAL_CODE_VERSION,
    AGENT_STORAGE_VERSION,
    AGENT_TARGET_RUNTIME,
    AGENT_VERSION,
)
from .._utils._project_files import (  # type: ignore
    FileInfo,
    InteractiveConflictHandler,
    UpdateEvent,
    compute_normalized_hash,
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

logger = logging.getLogger(__name__)


class SwFileHandler:
    """Handler for Studio Web file operations.

    This class encapsulates all file operations for UiPath Studio Web projects,
    including uploading, updating, deleting, and managing project structure.

    Attributes:
        directory: Local project directory
        include_uv_lock: Whether to include uv.lock file
    """

    def __init__(
        self,
        project_id: str,
        directory: str,
        include_uv_lock: bool = True,
        conflict_handler: Optional[InteractiveConflictHandler] = None,
    ) -> None:
        """Initialize the SwFileHandler.

        Args:
            project_id: The ID of the UiPath project
            directory: Local project directory
            include_uv_lock: Whether to include uv.lock file
            conflict_handler: Optional handler for file conflicts
        """
        self.directory = directory
        self.include_uv_lock = include_uv_lock
        self.console = ConsoleLogger()
        self._studio_client = StudioClient(project_id)
        self._project_structure: Optional[ProjectStructure] = None
        self._conflict_handler = conflict_handler or InteractiveConflictHandler(
            operation="push"
        )

    def _get_folder_by_name(
        self, structure: ProjectStructure, folder_name: str
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
    ) -> dict[str, ProjectFile]:
        """Get all files from the project structure indexed by name.

        Args:
            structure: The project structure

        Returns:
            files:  dictionary with file paths as keys
        """
        files: dict[str, ProjectFile] = {}
        self.collect_all_files(structure, files)

        return files

    async def _process_file_uploads(
        self,
        local_files: list[FileInfo],
        remote_files: Dict[str, ProjectFile],
    ) -> list[UpdateEvent]:
        """Process all file uploads.

        This method:
        1. Compares local files with remote files
        2. Builds a structural migration with added/modified/deleted resources
        3. Performs the structural migration
        4. Cleans up empty folders

        Args:
            local_files: List of files to upload
            remote_files: Dictionary of existing files

        Returns:
            List of FileOperationUpdate objects describing all file operations

        Raises:
            Exception: If any file upload fails
        """
        structural_migration = StructuralMigration(
            deleted_resources=[], added_resources=[], modified_resources=[]
        )
        processed_source_files: Set[str] = set()
        updates: list[UpdateEvent] = []

        for local_file in local_files:
            if not os.path.exists(local_file.file_path):
                logger.info(f"File not found: '{local_file.file_path}'")
                continue

            remote_file = remote_files.get(
                local_file.relative_path.replace("\\", "/"), None
            )

            if remote_file:
                processed_source_files.add(remote_file.id)

                try:
                    remote_response = (
                        await self._studio_client.download_project_file_async(
                            remote_file
                        )
                    )
                    remote_content = remote_response.read().decode("utf-8")
                    remote_hash = compute_normalized_hash(remote_content)

                    with open(local_file.file_path, "r", encoding="utf-8") as f:
                        local_content = f.read()
                        local_hash = compute_normalized_hash(local_content)

                    # Only update if content differs and user confirms
                    if local_hash != remote_hash:
                        if self._conflict_handler.should_overwrite(
                            local_file.relative_path,
                            remote_hash,
                            local_hash,
                            local_full_path=os.path.abspath(local_file.file_path),
                        ):
                            structural_migration.modified_resources.append(
                                ModifiedResource(
                                    id=remote_file.id,
                                    content_file_path=local_file.file_path,
                                )
                            )
                            updates.append(
                                UpdateEvent(
                                    file_path=local_file.file_path,
                                    status="updating",
                                    message=f"Updating '{local_file.file_name}'",
                                )
                            )
                        else:
                            updates.append(
                                UpdateEvent(
                                    file_path=local_file.file_path,
                                    status="skipped",
                                    message=f"Skipped '{local_file.file_name}'",
                                )
                            )
                    else:
                        # Content is the same, no need to update
                        updates.append(
                            UpdateEvent(
                                file_path=local_file.file_path,
                                status="up_to_date",
                                message=f"File '{local_file.file_name}' is up to date",
                            )
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to compare file '{local_file.file_path}': {e}"
                    )
                    # If comparison fails, proceed with update
                    structural_migration.modified_resources.append(
                        ModifiedResource(
                            id=remote_file.id, content_file_path=local_file.file_path
                        )
                    )
                    updates.append(
                        UpdateEvent(
                            file_path=local_file.file_path,
                            status="updating",
                            message=f"Updating '{local_file.file_name}'",
                        )
                    )
            else:
                # File doesn't exist remotely - mark for upload
                parent_path = os.path.dirname(local_file.relative_path)
                structural_migration.added_resources.append(
                    AddedResource(
                        content_file_path=local_file.file_path,
                        parent_path=f"{parent_path}" if parent_path != "" else None,
                    )
                )
                updates.append(
                    UpdateEvent(
                        file_path=local_file.file_path,
                        status="uploading",
                        message=f"Uploading '{local_file.file_name}'",
                    )
                )

        # Identify and add deleted files (files that exist remotely but not locally)
        deleted_files = self._collect_deleted_files(
            remote_files,
            processed_source_files,
            files_to_ignore=["agent.json"],
            directories_to_ignore=[
                name
                for name, condition in [
                    ("evals", not UiPathConfig.has_legacy_eval_folder),
                    ("evaluations", not UiPathConfig.has_eval_folder),
                ]
                if condition
            ],
        )
        structural_migration.deleted_resources.extend(deleted_files)

        # Add delete updates
        for file_id in deleted_files:
            file_name = next(
                (name for name, f in remote_files.items() if f.id == file_id),
                file_id,
            )
            updates.append(
                UpdateEvent(
                    file_path=file_name,
                    status="deleting",
                    message=f"Deleting '{file_name}'",
                )
            )

        # Load uipath.json configuration
        with open(os.path.join(self.directory, "uipath.json"), "r") as f:
            uipath_config = json.load(f)

        # Prepare agent.json migration (may download existing file to increment version)
        agent_update = await self._prepare_agent_json_migration(
            structural_migration, remote_files, uipath_config
        )
        if agent_update:
            updates.append(agent_update)

        # Perform the structural migration (uploads/updates/deletes all files)
        await self._studio_client.perform_structural_migration_async(
            structural_migration
        )

        # Clean up empty folders after migration
        await self._cleanup_empty_folders()

        return updates

    def _collect_deleted_files(
        self,
        remote_files: Dict[str, ProjectFile],
        processed_source_file_ids: Set[str],
        files_to_ignore: list[str] | None = None,
        directories_to_ignore: list[str] | None = None,
    ) -> set[str]:
        """Identify remote files that no longer exist locally.

        Args:
            remote_files: Dictionary of existing remote files
            processed_source_file_ids: Set of file IDs that were processed (exist locally)

        Returns:
            Set of file IDs to delete
        """
        deleted_file_ids: Set[str] = set()

        if not files_to_ignore:
            files_to_ignore = []

        if not directories_to_ignore:
            directories_to_ignore = []

        for file_path, remote_file in remote_files.items():
            if any(
                [
                    file_path.startswith(directory_name)
                    for directory_name in directories_to_ignore
                ]
            ):
                continue
            if (
                remote_file.id not in processed_source_file_ids
                and remote_file.name not in files_to_ignore
            ):
                deleted_file_ids.add(remote_file.id)

        return deleted_file_ids

    async def _cleanup_empty_folders(self) -> None:
        """Delete empty folders from the project structure.

        This method:
        1. Gets the current project structure
        2. Recursively finds all empty folders
        3. Deletes each empty folder
        """
        structure = await self._studio_client.get_project_structure_async()

        empty_folders = self._find_empty_folders(structure)

        if empty_folders:
            for folder in empty_folders:
                await self._studio_client.delete_item_async(folder["id"])
                logger.info(f"Deleted empty folder: '{folder['name']}'")

    def _find_empty_folders(self, folder: ProjectFolder) -> list[dict[str, str]]:
        """Recursively find all empty folders.

        Args:
            folder: The folder to check

        Returns:
            List of empty folder info dictionaries with 'id' and 'name' keys
        """
        empty_folders: list[dict[str, str]] = []

        for subfolder in folder.folders:
            # Recursively check subfolders first
            empty_folders.extend(self._find_empty_folders(subfolder))

            # Check if current subfolder is empty after processing its children
            if self._is_folder_empty(subfolder):
                if subfolder.id is not None:
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

    async def _prepare_agent_json_migration(
        self,
        structural_migration: StructuralMigration,
        remote_files: Dict[str, ProjectFile],
        uipath_config: Dict[str, Any],
    ) -> Optional[UpdateEvent]:
        """Prepare agent.json to be included in the same structural migration.

        This method:
        1. Extracts author from JWT token or pyproject.toml
        2. Downloads existing agent.json if it exists to increment code version
        3. Builds complete agent.json structure
        4. Adds to structural migration as modified or added resource

        Args:
            structural_migration: The structural migration to add resources to
            remote_files: Dictionary of remote files
            uipath_config: Configuration from uipath.json

        Returns:
            FileOperationUpdate describing the operation, or None if error occurred
        """

        def get_author_from_token_or_toml() -> str:
            """Get author from JWT token or fall back to pyproject.toml."""
            try:
                preferred_username = get_claim_from_token("preferred_username")
                if preferred_username:
                    return preferred_username
            except Exception:
                # fallback to toml
                pass

            toml_data = read_toml_project(
                os.path.join(self.directory, "pyproject.toml")
            )
            return toml_data.get("authors", "").strip()

        author = get_author_from_token_or_toml()

        # Initialize agent.json structure with metadata
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
            "bindings": uipath_config.get(
                "bindings", {"version": "2.0", "resources": []}
            ),
            "inputSchema": {},
            "outputSchema": {},
            "settings": {},
            # TODO: remove this after validation check gets removed on SW side
            "entryPoints": [{}],
        }

        existing = remote_files.get("agent.json")
        if existing:
            # Agent.json exists - download and increment version
            try:
                existing_agent_json = (
                    await self._studio_client.download_project_file_async(existing)
                ).json()
                version_parts = existing_agent_json["metadata"]["codeVersion"].split(
                    "."
                )
                if len(version_parts) >= 3:
                    # Increment patch version (0.1.0 -> 0.1.1)
                    version_parts[-1] = str(int(version_parts[-1]) + 1)
                    agent_json["metadata"]["codeVersion"] = ".".join(version_parts)
                else:
                    # Invalid version format, use default with patch = 1
                    agent_json["metadata"]["codeVersion"] = (
                        AGENT_INITIAL_CODE_VERSION[:-1] + "1"
                    )
            except Exception:
                logger.info(
                    "Could not parse existing 'agent.json' file, using default version"
                )

            structural_migration.modified_resources.append(
                ModifiedResource(
                    id=existing.id,
                    content_string=json.dumps(agent_json),
                )
            )
            return UpdateEvent(
                file_path="agent.json",
                status="updating",
                message="Updating 'agent.json'",
            )
        else:
            # Agent.json doesn't exist - create new one
            logger.info(
                "'agent.json' file does not exist in Studio Web project, initializing using default version"
            )
            structural_migration.added_resources.append(
                AddedResource(
                    file_name="agent.json",
                    content_string=json.dumps(agent_json),
                )
            )
            return UpdateEvent(
                file_path="agent.json",
                status="uploading",
                message="Uploading 'agent.json'",
            )

    async def upload_source_files(
        self, settings: Optional[dict[str, Any]]
    ) -> AsyncIterator[UpdateEvent]:
        """Main method to upload source files to the UiPath project.

        This method:
        1. Gets project structure (or creates if it doesn't exist)
        2. Collects local files to upload
        3. Processes file uploads (yields progress updates)
        4. Performs structural migration
        5. Cleans up empty folders

        Args:
            settings: File handling settings (includes/excludes)

        Yields:
            FileOperationUpdate: Progress updates for each file operation

        Raises:
            Exception: If any step in the process fails
        """
        # Get or create project structure
        try:
            structure = await self._studio_client.get_project_structure_async()
        except EnrichedException as e:
            if e.status_code == 404:
                # Project structure doesn't exist - create empty structure and lock
                structure = ProjectStructure(name="", files=[], folders=[])
                await self._studio_client._put_lock()
            else:
                raise

        remote_files = self._get_remote_files(structure)

        # Get files to upload and process them
        local_files = files_to_include(
            settings,
            self.directory,
            self.include_uv_lock,
        )

        updates = await self._process_file_uploads(local_files, remote_files)

        # Yield all updates
        for update in updates:
            yield update

    async def _process_file_sync(
        self,
        local_file_path: str,
        remote_files: Dict[str, ProjectFile],
        parent_path: str,
        destination_prefix: str,
        structural_migration: StructuralMigration,
        processed_ids: Set[str],
    ) -> None:
        """Process a single local file for upload or update to remote.

        Args:
            local_file_path: Path to the local file to sync
            remote_files: Dictionary of remote files indexed by filename
            parent_path: Parent path for new file creation
            destination_prefix: Prefix for destination path in console output
            structural_migration: Migration object to append resources to
            processed_ids: Set to track processed remote file IDs
        """
        file_name = os.path.basename(local_file_path)
        remote_file = remote_files.get(file_name)
        destination = f"{destination_prefix}/{file_name}"

        if remote_file:
            processed_ids.add(remote_file.id)

            # Download remote file and compare with local
            try:
                remote_response = await self._studio_client.download_project_file_async(
                    remote_file
                )
                remote_content = remote_response.read().decode("utf-8")
                remote_hash = compute_normalized_hash(remote_content)

                with open(local_file_path, "r", encoding="utf-8") as f:
                    local_content = f.read()
                    local_hash = compute_normalized_hash(local_content)

                # Only update if content differs and user confirms
                if local_hash != remote_hash:
                    if self._conflict_handler.should_overwrite(
                        destination,
                        remote_hash,
                        local_hash,
                        local_full_path=os.path.abspath(local_file_path),
                    ):
                        structural_migration.modified_resources.append(
                            ModifiedResource(
                                id=remote_file.id, content_file_path=local_file_path
                            )
                        )
                        self.console.info(
                            f"Updating {click.style(destination, fg='yellow')}"
                        )
                    else:
                        self.console.info(
                            f"Skipped {click.style(destination, fg='bright_black')}"
                        )
                else:
                    # Content is the same, no need to update
                    self.console.info(f"File '{destination}' is up to date")
            except Exception as e:
                logger.warning(f"Failed to compare file '{local_file_path}': {e}")
                # If comparison fails, proceed with update
                structural_migration.modified_resources.append(
                    ModifiedResource(
                        id=remote_file.id, content_file_path=local_file_path
                    )
                )
                self.console.info(f"Updating {click.style(destination, fg='yellow')}")
        else:
            structural_migration.added_resources.append(
                AddedResource(
                    content_file_path=local_file_path, parent_path=parent_path
                )
            )
            self.console.info(f"Uploading to {click.style(destination, fg='cyan')}")

    def _collect_deleted_remote_files(
        self,
        remote_files: Dict[str, ProjectFile],
        processed_ids: Set[str],
        destination_prefix: str,
        structural_migration: StructuralMigration,
    ) -> None:
        """Collect remote files that no longer exist locally for deletion.

        Args:
            remote_files: Dictionary of remote files indexed by filename
            processed_ids: Set of remote file IDs that were processed
            destination_prefix: Prefix for destination path in console output
            structural_migration: Migration object to append deleted resources to
        """
        for file_name, remote_file in remote_files.items():
            if remote_file.id not in processed_ids:
                structural_migration.deleted_resources.append(remote_file.id)
                destination = f"{destination_prefix}/{file_name}"
                self.console.info(
                    f"Deleting {click.style(destination, fg='bright_red')}"
                )
