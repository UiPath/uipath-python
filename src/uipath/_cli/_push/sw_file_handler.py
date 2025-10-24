"""Studio Web File Handler for managing file operations in UiPath projects."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional, Set

import click

from ...models.exceptions import EnrichedException
from .._evals._helpers import (  # type: ignore
    register_evaluator,
    try_extract_file_and_class_name,
)
from .._utils._console import ConsoleLogger
from .._utils._constants import (
    AGENT_INITIAL_CODE_VERSION,
    AGENT_STORAGE_VERSION,
    AGENT_TARGET_RUNTIME,
    AGENT_VERSION,
)
from .._utils._project_files import (  # type: ignore
    FileInfo,
    FileOperationUpdate,
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
from .models import EvaluatorFileDetails

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
        root_files: Dict[str, ProjectFile],
    ) -> list[FileOperationUpdate]:
        """Process all file uploads to the source_code folder.

        This method:
        1. Compares local files with remote files
        2. Builds a structural migration with added/modified/deleted resources
        3. Prepares agent.json and entry-points.json
        4. Performs the structural migration
        5. Cleans up empty folders

        Args:
            local_files: List of files to upload
            source_code_files: Dictionary of existing remote files
            root_files: Dictionary of existing root-level files

        Returns:
            List of FileOperationUpdate objects describing all file operations

        Raises:
            Exception: If any file upload fails
        """
        structural_migration = StructuralMigration(
            deleted_resources=[], added_resources=[], modified_resources=[]
        )
        processed_source_files: Set[str] = set()
        updates: list[FileOperationUpdate] = []

        # Process each local file and build structural migration
        for local_file in local_files:
            if not os.path.exists(local_file.file_path):
                logger.info(f"File not found: '{local_file.file_path}'")
                continue

            # Skip agent.json as it's handled separately
            if local_file.file_name == "agent.json":
                continue

            remote_file = source_code_files.get(
                local_file.relative_path.replace("\\", "/"), None
            )

            if remote_file:
                # File exists remotely - mark for update
                processed_source_files.add(remote_file.id)
                structural_migration.modified_resources.append(
                    ModifiedResource(
                        id=remote_file.id, content_file_path=local_file.file_path
                    )
                )
                updates.append(
                    FileOperationUpdate(
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
                        parent_path=f"source_code/{parent_path}"
                        if parent_path != ""
                        else "source_code",
                    )
                )
                updates.append(
                    FileOperationUpdate(
                        file_path=local_file.file_path,
                        status="uploading",
                        message=f"Uploading '{local_file.file_name}'",
                    )
                )

        # Identify and add deleted files (files that exist remotely but not locally)
        deleted_files = self._collect_deleted_files(
            source_code_files, processed_source_files
        )
        structural_migration.deleted_resources.extend(deleted_files)

        # Add delete updates
        for file_id in deleted_files:
            file_name = next(
                (name for name, f in source_code_files.items() if f.id == file_id),
                file_id,
            )
            updates.append(
                FileOperationUpdate(
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
            structural_migration, root_files, uipath_config
        )
        if agent_update:
            updates.append(agent_update)

        # Prepare entry-points.json migration (may download existing file to merge)
        entry_points_update = await self._prepare_entrypoints_json_migration(
            structural_migration, root_files, uipath_config
        )
        if entry_points_update:
            updates.append(entry_points_update)

        # Perform the structural migration (uploads/updates/deletes all files)
        await self._studio_client.perform_structural_migration_async(
            structural_migration
        )

        # Clean up empty folders after migration
        await self._cleanup_empty_folders()

        return updates

    def _collect_deleted_files(
        self,
        source_code_files: Dict[str, ProjectFile],
        processed_source_file_ids: Set[str],
    ) -> set[str]:
        """Identify remote files that no longer exist locally.

        Args:
            source_code_files: Dictionary of existing remote files
            processed_source_file_ids: Set of file IDs that were processed (exist locally)

        Returns:
            Set of file IDs to delete
        """
        deleted_file_ids: Set[str] = set()

        for _, remote_file in source_code_files.items():
            if remote_file.id not in processed_source_file_ids:
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
        source_code_folder = self._get_folder_by_name(structure, "source_code")

        if not source_code_folder:
            return

        empty_folders = self._find_empty_folders(source_code_folder)

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

    async def _prepare_entrypoints_json_migration(
        self,
        structural_migration: StructuralMigration,
        root_files: Dict[str, ProjectFile],
        uipath_config: Dict[str, Any],
    ) -> Optional[FileOperationUpdate]:
        """Prepare entry-points.json to be included in the same structural migration.

        This method:
        1. Downloads existing entry-points.json if it exists
        2. Merges entryPoints from uipath.json config
        3. Adds to structural migration as modified or added resource

        Args:
            structural_migration: The structural migration to add resources to
            root_files: Dictionary of root-level files
            uipath_config: Configuration from uipath.json

        Returns:
            FileOperationUpdate describing the operation, or None if error occurred
        """
        existing = root_files.get("entry-points.json")

        if existing:
            # Entry-points.json exists - download and merge
            try:
                entry_points_json = (
                    await self._studio_client.download_project_file_async(existing)
                ).json()
                entry_points_json["entryPoints"] = uipath_config["entryPoints"]
            except Exception:
                logger.info(
                    "Could not parse existing 'entry-points.json' file, using default version"
                )
                # If parsing fails, create default structure
                entry_points_json = {
                    "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
                    "$id": "entry-points.json",
                    "entryPoints": uipath_config["entryPoints"],
                }

            structural_migration.modified_resources.append(
                ModifiedResource(
                    id=existing.id,
                    content_string=json.dumps(entry_points_json),
                )
            )
            return FileOperationUpdate(
                file_path="entry-points.json",
                status="updating",
                message="Updating 'entry-points.json'",
            )
        else:
            # Entry-points.json doesn't exist - create new one
            logger.info(
                "'entry-points.json' file does not exist in Studio Web project, initializing using default version"
            )
            entry_points_json = {
                "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
                "$id": "entry-points.json",
                "entryPoints": uipath_config["entryPoints"],
            }
            structural_migration.added_resources.append(
                AddedResource(
                    file_name="entry-points.json",
                    content_string=json.dumps(entry_points_json),
                )
            )
            return FileOperationUpdate(
                file_path="entry-points.json",
                status="uploading",
                message="Uploading 'entry-points.json'",
            )

    async def _prepare_agent_json_migration(
        self,
        structural_migration: StructuralMigration,
        root_files: Dict[str, ProjectFile],
        uipath_config: Dict[str, Any],
    ) -> Optional[FileOperationUpdate]:
        """Prepare agent.json to be included in the same structural migration.

        This method:
        1. Extracts author from JWT token or pyproject.toml
        2. Downloads existing agent.json if it exists to increment code version
        3. Builds complete agent.json structure
        4. Adds to structural migration as modified or added resource

        Args:
            structural_migration: The structural migration to add resources to
            root_files: Dictionary of root-level files
            uipath_config: Configuration from uipath.json

        Returns:
            FileOperationUpdate describing the operation, or None if error occurred
        """

        def get_author_from_token_or_toml() -> str:
            """Get author from JWT token or fall back to pyproject.toml."""
            import jwt

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

            toml_data = read_toml_project(
                os.path.join(self.directory, "pyproject.toml")
            )
            return toml_data.get("authors", "").strip()

        # Extract input and output schemas from entrypoints
        try:
            input_schema = uipath_config["entryPoints"][0]["input"]
            output_schema = uipath_config["entryPoints"][0]["output"]
        except (FileNotFoundError, KeyError) as e:
            logger.error(
                f"Unable to extract entrypoints from configuration file. Please run 'uipath init' : {str(e)}",
            )
            return None

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
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "bindings": uipath_config.get(
                "bindings", {"version": "2.0", "resources": []}
            ),
            "settings": {},
            # TODO: remove this after validation check gets removed on SW side
            "entryPoints": [{}],
        }

        existing = root_files.get("agent.json")
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
            return FileOperationUpdate(
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
            return FileOperationUpdate(
                file_path="agent.json",
                status="uploading",
                message="Uploading 'agent.json'",
            )

    async def upload_source_files(
        self, settings: Optional[dict[str, Any]]
    ) -> AsyncIterator[FileOperationUpdate]:
        """Main method to upload source files to the UiPath project.

        This method:
        1. Gets project structure (or creates if doesn't exist)
        2. Creates source_code folder if needed
        3. Collects local files to upload
        4. Processes file uploads (yields progress updates)
        5. Performs structural migration
        6. Cleans up empty folders

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

        source_code_folder = self._get_folder_by_name(structure, "source_code")
        root_files, source_code_files = self._get_remote_files(
            structure, source_code_folder
        )

        # Create source_code folder if it doesn't exist
        if not source_code_folder:
            await self._studio_client.create_folder_async("source_code")
            yield FileOperationUpdate(
                file_path="source_code",
                status="created_folder",
                message="Created 'source_code' folder.",
            )
            source_code_files = {}

        # Get files to upload and process them
        files = files_to_include(
            settings,
            self.directory,
            self.include_uv_lock,
            directories_to_ignore=["evals"],
        )

        # Process all files and get updates (this includes HTTP calls for agent.json/entry-points.json)
        updates = await self._process_file_uploads(files, source_code_files, root_files)

        # Yield all updates
        for update in updates:
            yield update

    def _extract_evaluator_details(self, file_path: str) -> tuple[bool, str]:
        """Return whether an evaluator JSON file has a version property and the custom-evaluator python file (if exists).

        Args:
            file_path: Path to the file to check

        Returns:
            tuple[bool, str]: A tuple containing:
                        - A boolean indicating whether the JSON file contains a "version" property.
                        - The path to the custom-evaluator Python file, if it exists; otherwise, an empty string.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _, file_name, _ = try_extract_file_and_class_name(
                data.get("evaluatorSchema", "")
            )
            return "version" in data, file_name
        except (json.JSONDecodeError, FileNotFoundError):
            return False, ""

    def _get_coded_evals_files(self) -> tuple[list[EvaluatorFileDetails], list[str]]:
        """Get coded-evals files from local evals directory.

        Returns:
            Tuple of (evaluator_files, eval_set_files) with version property
        """
        evaluator_files: list[EvaluatorFileDetails] = []
        eval_set_files = []

        # Check {self.directory}/evals/evaluators/ for files with version property
        evaluators_dir = os.path.join(self.directory, "evals", "evaluators")
        if os.path.exists(evaluators_dir):
            for file_name in os.listdir(evaluators_dir):
                if file_name.endswith(".json"):
                    file_path = os.path.join(evaluators_dir, file_name)
                    version, file_name = self._extract_evaluator_details(file_path)
                    if version:
                        evaluator_files.append(
                            EvaluatorFileDetails(
                                path=file_path, custom_evaluator_file_name=file_name
                            )
                        )

        # Check {self.directory}/evals/eval-sets/ for files with version property
        eval_sets_dir = os.path.join(self.directory, "evals", "eval-sets")
        if os.path.exists(eval_sets_dir):
            for file_name in os.listdir(eval_sets_dir):
                if file_name.endswith(".json"):
                    file_path = os.path.join(eval_sets_dir, file_name)
                    version, _ = self._extract_evaluator_details(file_path)
                    if version:
                        eval_set_files.append(file_path)

        return evaluator_files, eval_set_files

    def _get_subfolder_by_name(
        self, parent_folder: ProjectFolder, subfolder_name: str
    ) -> Optional[ProjectFolder]:
        """Get a subfolder from within a parent folder by name.

        Args:
            parent_folder: The parent folder to search within
            subfolder_name: Name of the subfolder to find

        Returns:
            Optional[ProjectFolder]: The found subfolder or None
        """
        for folder in parent_folder.folders:
            if folder.name == subfolder_name:
                return folder
        return None

    async def _ensure_coded_evals_structure(
        self, structure: ProjectStructure
    ) -> ProjectFolder:
        """Ensure coded-evals folder structure exists in remote project.

        Args:
            structure: Current project structure

        Returns:
            ProjectFolder: The coded-evals folder
        """
        coded_evals_folder = self._get_folder_by_name(structure, "coded-evals")

        if not coded_evals_folder:
            coded_evals_id = await self._studio_client.create_folder_async(
                "coded-evals"
            )
            self.console.success(
                f"Created {click.style('coded-evals', fg='cyan')} folder"
            )

            await self._studio_client.create_folder_async("evaluators", coded_evals_id)
            self.console.success(
                f"Created {click.style('coded-evals/evaluators', fg='cyan')} folder"
            )

            await self._studio_client.create_folder_async("eval-sets", coded_evals_id)
            self.console.success(
                f"Created {click.style('coded-evals/eval-sets', fg='cyan')} folder"
            )

            # Refresh structure to get the new folders
            structure = await self._studio_client.get_project_structure_async()
            coded_evals_folder = self._get_folder_by_name(structure, "coded-evals")
            assert coded_evals_folder, "Coded-evals folder uploaded but not found."

        return coded_evals_folder

    def _collect_files_from_folder(
        self, folder: Optional[ProjectFolder]
    ) -> Dict[str, ProjectFile]:
        files: Dict[str, ProjectFile] = {}
        if folder:
            for file in folder.files:
                files[file.name] = file
        return files

    def _process_file_sync(
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
            structural_migration.modified_resources.append(
                ModifiedResource(id=remote_file.id, content_file_path=local_file_path)
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

    async def upload_coded_evals_files(self) -> None:
        """Upload coded-evals files (files with version property) to Studio Web.

        This method:
        1. Scans local evals/evaluators and evals/eval-sets for files with version property
        2. Ensures coded-evals folder structure exists in remote project
        3. Uploads the files to coded-evals/evaluators and coded-evals/eval-sets respectively
        4. Deletes remote files that no longer exist locally (consistent with source file behavior)
        """
        evaluator_details, eval_set_files = self._get_coded_evals_files()

        structure = await self._studio_client.get_project_structure_async()
        coded_evals_folder = self._get_folder_by_name(structure, "coded-evals")

        # If no coded-evals folder exists and no local files, nothing to do
        if not coded_evals_folder and not evaluator_details and not eval_set_files:
            return

        # Ensure folder structure exists if we have local files
        if evaluator_details or eval_set_files:
            await self._ensure_coded_evals_structure(structure)
            # Refresh structure to get the new folders
            structure = await self._studio_client.get_project_structure_async()
            coded_evals_folder = self._get_folder_by_name(structure, "coded-evals")

        if not coded_evals_folder:
            return  # Nothing to sync

        evaluators_folder = self._get_subfolder_by_name(
            coded_evals_folder, "evaluators"
        )
        if evaluators_folder:
            eval_sets_folder = self._get_subfolder_by_name(
                coded_evals_folder, "eval-sets"
            )
            custom_evaluators_folder = self._get_subfolder_by_name(
                evaluators_folder, "custom"
            )
            evaluator_types_folder = None
            if custom_evaluators_folder:
                evaluator_types_folder = self._get_subfolder_by_name(
                    custom_evaluators_folder, "types"
                )

            remote_evaluator_files = self._collect_files_from_folder(evaluators_folder)
            remote_eval_set_files = self._collect_files_from_folder(eval_sets_folder)
            remote_custom_evaluator_files = self._collect_files_from_folder(
                custom_evaluators_folder
            )
            remote_custom_evaluator_type_files = self._collect_files_from_folder(
                evaluator_types_folder
            )

            # Create structural migration for coded-evals files
            structural_migration = StructuralMigration(
                deleted_resources=[], added_resources=[], modified_resources=[]
            )

            processed_evaluator_ids: Set[str] = set()
            processed_eval_set_ids: Set[str] = set()
            processed_custom_evaluator_ids: Set[str] = set()
            processed_evaluator_type_ids: Set[str] = set()

            for evaluator in evaluator_details:
                if evaluator.is_custom:
                    evaluator_schema_file_path, evaluator_types_file_path = (
                        register_evaluator(evaluator.custom_evaluator_file_name)
                    )

                    self._process_file_sync(
                        evaluator_schema_file_path,
                        remote_custom_evaluator_files,
                        "coded-evals/evaluators/custom",
                        "coded-evals/evaluators/custom",
                        structural_migration,
                        processed_custom_evaluator_ids,
                    )

                    self._process_file_sync(
                        evaluator_types_file_path,
                        remote_custom_evaluator_type_files,
                        "coded-evals/evaluators/custom/types",
                        "coded-evals/evaluators/custom/types",
                        structural_migration,
                        processed_evaluator_type_ids,
                    )

                self._process_file_sync(
                    evaluator.path,
                    remote_evaluator_files,
                    "coded-evals/evaluators",
                    "coded-evals/evaluators",
                    structural_migration,
                    processed_evaluator_ids,
                )

            for eval_set_file in eval_set_files:
                self._process_file_sync(
                    eval_set_file,
                    remote_eval_set_files,
                    "coded-evals/eval-sets",
                    "coded-evals/eval-sets",
                    structural_migration,
                    processed_eval_set_ids,
                )

            self._collect_deleted_remote_files(
                remote_evaluator_files,
                processed_evaluator_ids,
                "coded-evals/evaluators",
                structural_migration,
            )

            self._collect_deleted_remote_files(
                remote_eval_set_files,
                processed_eval_set_ids,
                "coded-evals/eval-sets",
                structural_migration,
            )

            self._collect_deleted_remote_files(
                remote_custom_evaluator_files,
                processed_custom_evaluator_ids,
                "coded-evals/evaluators/custom",
                structural_migration,
            )

            self._collect_deleted_remote_files(
                remote_custom_evaluator_type_files,
                processed_evaluator_type_ids,
                "coded-evals/evaluators/custom/types",
                structural_migration,
            )

            if (
                structural_migration.added_resources
                or structural_migration.modified_resources
                or structural_migration.deleted_resources
            ):
                await self._studio_client.perform_structural_migration_async(
                    structural_migration
                )
