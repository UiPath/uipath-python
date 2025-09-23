import json
import os
from functools import wraps
from pathlib import PurePath
from typing import Any, Callable, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from uipath._utils.constants import HEADER_SW_LOCK_KEY
from uipath.models.exceptions import EnrichedException


class ProjectFile(BaseModel):
    """Model representing a file in a UiPath project.

    Attributes:
        id: The unique identifier of the file
        name: The name of the file
        is_main: Whether this is a main file
        file_type: The type of the file
        is_entry_point: Whether this is an entry point
        ignored_from_publish: Whether this file is ignored during publish
        app_form_id: The ID of the associated app form
        external_automation_id: The ID of the external automation
        test_case_id: The ID of the associated test case
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    id: str = Field(alias="id")
    name: str = Field(alias="name")
    is_main: Optional[bool] = Field(default=None, alias="isMain")
    file_type: Optional[str] = Field(default=None, alias="fileType")
    is_entry_point: Optional[bool] = Field(default=None, alias="isEntryPoint")
    ignored_from_publish: Optional[bool] = Field(
        default=None, alias="ignoredFromPublish"
    )
    app_form_id: Optional[str] = Field(default=None, alias="appFormId")
    external_automation_id: Optional[str] = Field(
        default=None, alias="externalAutomationId"
    )
    test_case_id: Optional[str] = Field(default=None, alias="testCaseId")

    @field_validator("file_type", mode="before")
    @classmethod
    def convert_file_type(cls, v: Union[str, int, None]) -> Optional[str]:
        """Convert numeric file type to string.

        Args:
            v: The value to convert

        Returns:
            Optional[str]: The converted value or None
        """
        if isinstance(v, int):
            return str(v)
        return v


class ProjectFolder(BaseModel):
    """Model representing a folder in a UiPath project structure.

    Attributes:
        id: The unique identifier of the folder. Root folder id may be None.
        name: The name of the folder
        folders: List of subfolders
        files: List of files in the folder
        folder_type: The type of the folder
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    id: Optional[str] = Field(default=None, alias="id")
    name: str = Field(alias="name")
    folders: List["ProjectFolder"] = Field(default_factory=list)
    files: List[ProjectFile] = Field(default_factory=list)
    folder_type: Optional[str] = Field(default=None, alias="folderType")

    @field_validator("folder_type", mode="before")
    @classmethod
    def convert_folder_type(cls, v: Union[str, int, None]) -> Optional[str]:
        """Convert numeric folder type to string.

        Args:
            v: The value to convert

        Returns:
            Optional[str]: The converted value or None
        """
        if isinstance(v, int):
            return str(v)
        return v


class ProjectStructure(ProjectFolder):
    """Model representing the complete file structure of a UiPath project.

    Attributes:
        id: The unique identifier of the root folder (optional)
        name: The name of the root folder (optional)
        folders: List of folders in the project
        files: List of files at the root level
        folder_type: The type of the root folder (optional)
    """

    pass


class LockInfo(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    project_lock_key: Optional[str] = Field(alias="projectLockKey")
    solution_lock_key: Optional[str] = Field(alias="solutionLockKey")


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


def resolve_path(
    folder: ProjectFolder,
    path: PurePath,
) -> ProjectFile | ProjectFolder:
    """Resolve a path relative to the folder.

    Args:
        folder: Project folder
        path: Path relative to the folder

    Returns: The resolved folder or file. If resolution fails, an assertion is raised.
    """
    root = path.parts
    while len(root) > 1:
        child = next(
            (folder for folder in folder.folders if folder.name == root[0]), None
        )
        assert child, "Path not found."
        folder = child
        root = root[1:]
    file = next((f for f in folder.files if f.name == root[0]), None)
    child = next((folder for folder in folder.folders if folder.name == root[0]), None)
    resolved = file or child
    assert resolved, "Path not found."
    return resolved


class AddedResource(BaseModel):
    """Represents a new file to be added during a structural migration."""

    content_file_path: Optional[str] = None
    parent_path: Optional[str] = None
    file_name: Optional[str] = None
    content_string: Optional[str] = None


class ModifiedResource(BaseModel):
    """Represents a file update during a structural migration."""

    id: str
    content_file_path: Optional[str] = None
    content_string: Optional[str] = None


class StructuralMigration(BaseModel):
    deleted_resources: List[str]
    added_resources: List[AddedResource]
    modified_resources: List[ModifiedResource]


def with_lock_retry(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            lock_info = await self._retrieve_lock()
            if not lock_info.project_lock_key:
                raise RuntimeError("Failed to retrieve project lock key.")

            headers = kwargs.get("headers", {}) or {}
            headers[HEADER_SW_LOCK_KEY] = lock_info.project_lock_key
            kwargs["headers"] = headers

            return await func(self, *args, **kwargs)
        except EnrichedException as e:
            if e.status_code == 423:
                from uipath._cli._utils._console import ConsoleLogger

                console = ConsoleLogger()
                console.error(
                    "The project is temporarily locked. This could be due to modifications or active processes. Please wait a moment and try again."
                )
            raise

    return wrapper


class StudioClient:
    def __init__(self, project_id: str):
        from uipath import UiPath

        self.uipath: UiPath = UiPath()
        self.file_operations_base_url: str = (
            f"/studio_/backend/api/Project/{project_id}/FileOperations"
        )
        self._lock_operations_base_url: str = (
            f"/studio_/backend/api/Project/{project_id}/Lock"
        )

    async def get_project_structure_async(self) -> ProjectStructure:
        """Retrieve the project's file structure from UiPath Cloud.

        Makes an API call to fetch the complete file structure of a project,
        including all files and folders. The response is validated against
        the ProjectStructure model.

        Returns:
            ProjectStructure: The complete project structure
        """
        response = await self.uipath.api_client.request_async(
            "GET",
            url=f"{self.file_operations_base_url}/Structure",
            scoped="org",
        )

        return ProjectStructure.model_validate(response.json())

    @with_lock_retry
    async def create_folder_async(
        self,
        folder_name: str,
        parent_id: Optional[str] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a folder in the project.

        Args:
            folder_name: Name of the folder to create
            parent_id: Optional parent folder ID
            headers: HTTP headers (automatically injected by decorator)

        Returns:
            str: The created folder ID
        """
        data = {"name": folder_name}
        if parent_id:
            data["parent_id"] = parent_id
        response = await self.uipath.api_client.request_async(
            "POST",
            url=f"{self.file_operations_base_url}/Folder",
            scoped="org",
            json=data,
            headers=headers or {},
        )
        return response.json()

    async def download_file_async(self, file_id: str) -> Any:
        response = await self.uipath.api_client.request_async(
            "GET",
            url=f"{self.file_operations_base_url}/File/{file_id}",
            scoped="org",
        )
        return response

    @with_lock_retry
    async def upload_file_async(
        self,
        *,
        local_file_path: Optional[str] = None,
        file_content: Optional[str] = None,
        file_name: str,
        folder: Optional[ProjectFolder] = None,
        remote_file: Optional[ProjectFile] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> tuple[str, str]:
        if local_file_path:
            with open(local_file_path, "rb") as f:
                file_content = f.read()  # type: ignore
        files_data = {"file": (file_name, file_content, "application/octet-stream")}

        if remote_file:
            # File exists in source_code folder, use PUT to update
            response = await self.uipath.api_client.request_async(
                "PUT",
                files=files_data,
                url=f"{self.file_operations_base_url}/File/{remote_file.id}",
                scoped="org",
                headers=headers or {},
            )
            action = "Updated"
        else:
            response = await self.uipath.api_client.request_async(
                "POST",
                url=f"{self.file_operations_base_url}/File",
                data={"parentId": folder.id} if folder else None,
                files=files_data,
                scoped="org",
                headers=headers or {},
            )
            action = "Uploaded"

        # response contains only the uploaded file identifier
        return response.json(), action

    @with_lock_retry
    async def delete_item_async(
        self,
        item_id: str,
        headers: Optional[dict[str, Any]] = None,
    ) -> None:
        await self.uipath.api_client.request_async(
            "DELETE",
            url=f"{self.file_operations_base_url}/Delete/{item_id}",
            scoped="org",
            headers=headers or {},
        )

    def _resolve_content_and_filename(
        self,
        *,
        content_string: Optional[str],
        content_file_path: Optional[str],
        file_name: Optional[str] = None,
        modified: bool = False,
    ) -> tuple[bytes, Optional[str]]:
        """Resolve multipart content bytes and filename for a resource.

        Args:
            content_string: Inline content as a string.
            content_file_path: Path to a local file to read if inline content is not provided.
            file_name: Explicit filename to use when adding a new resource.

        Returns:
            A tuple of (content_bytes, filename).

        Raises:
            FileNotFoundError: If a provided file path does not exist.
            ValueError: If a filename cannot be determined.
        """
        content_bytes: bytes = b""
        resolved_name: Optional[str] = None
        if content_string is not None:
            content_bytes = content_string.encode("utf-8")
        elif content_file_path:
            if os.path.exists(content_file_path):
                with open(content_file_path, "rb") as f:
                    content_bytes = f.read()
            else:
                raise FileNotFoundError(f"File not found: {content_file_path}")

        if file_name:
            resolved_name = file_name
        elif content_file_path:
            resolved_name = os.path.basename(content_file_path)
        elif not modified:
            raise ValueError(
                "Unable to determine filename for multipart upload. "
                "When providing inline content (content_string), you must also provide file_name. "
                "Alternatively, set content_file_path so the filename can be inferred. "
                f"Received file_name={file_name!r}, content_file_path={content_file_path!r}."
            )

        return content_bytes, resolved_name

    @with_lock_retry
    async def perform_structural_migration_async(
        self,
        structural_migration: StructuralMigration,
        headers: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Perform structural migration of project files.

        Args:
            structural_migration: The structural migration data containing deleted and added resources
            headers: HTTP headers (automatically injected by decorator)

        Returns:
            Any: The API response
        """
        files: Any = []
        deleted_resources_json = json.dumps(structural_migration.deleted_resources)

        files.append(
            (
                "DeletedResources",
                (None, deleted_resources_json),
            )
        )
        for i, added_resource in enumerate(structural_migration.added_resources):
            content_bytes, filename = self._resolve_content_and_filename(
                content_string=added_resource.content_string,
                content_file_path=added_resource.content_file_path,
                file_name=added_resource.file_name,
            )

            files.append((f"AddedResources[{i}].Content", (filename, content_bytes)))

            if added_resource.parent_path:
                files.append(
                    (
                        f"AddedResources[{i}].ParentPath",
                        (None, added_resource.parent_path),
                    )
                )

        for i, modified_resource in enumerate(structural_migration.modified_resources):
            content_bytes, _ = self._resolve_content_and_filename(
                content_string=modified_resource.content_string,
                content_file_path=modified_resource.content_file_path,
                modified=True,
            )

            files.append((f"ModifiedResources[{i}].Content", content_bytes))
            files.append(
                (
                    f"ModifiedResources[{i}].Id",
                    (None, modified_resource.id),
                )
            )

        response = await self.uipath.api_client.request_async(
            "POST",
            url=f"{self.file_operations_base_url}/StructuralMigration",
            scoped="org",
            files=files,
            headers=headers or {},
        )

        return response

    async def _retrieve_lock(self) -> LockInfo:
        response = await self.uipath.api_client.request_async(
            "GET",
            url=f"{self._lock_operations_base_url}",
            scoped="org",
        )
        return LockInfo.model_validate(response.json())
