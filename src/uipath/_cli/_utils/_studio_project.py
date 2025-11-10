import json
import os
from enum import Enum
from functools import wraps
from pathlib import PurePath
from typing import Any, Callable, List, Optional, Union

import click
from pydantic import BaseModel, ConfigDict, Field, field_validator

from uipath import UiPath
from uipath._config import UiPathConfig
from uipath._utils._bindings import ResourceOverwrite, ResourceOverwriteParser
from uipath._utils.constants import ENV_TENANT_ID, HEADER_SW_LOCK_KEY, HEADER_TENANT_ID
from uipath.models.exceptions import EnrichedException
from uipath.tracing import traced


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


class Severity(str, Enum):
    """Severity level for virtual resource operation results."""

    SUCCESS = "success"
    ATTENTION = "attention"
    WARN = "warn"


class VirtualResourceRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )

    kind: str = Field(alias="kind")
    name: str = Field(alias="name")
    type: Optional[str] = Field(default=None, alias="type")
    activity_name: Optional[str] = Field(default=None, alias="activityName")
    api_version: Optional[str] = Field(default=None, alias="apiVersion")


class VirtualResourceResult(BaseModel):
    """Result of a virtual resource creation operation.

    Attributes:
        severity: The severity level (log, warn or attention)
        message: The result message with styling
    """

    severity: Severity
    message: str


class ResourceOverwriteData(BaseModel):
    """Represents the overwrite details from the API response.

    Attributes:
        name: The name of the resource being overwritten
        folder_path: The folder path of the overwrite resource
    """

    model_config = ConfigDict(
        populate_by_name=True,
    )

    name: str = Field(alias="name")
    folder_path: str = Field(alias="folderPath")


def get_folder_by_name(
    structure: ProjectStructure, folder_name: str | None
) -> Optional[ProjectFolder]:
    """Get a folder from the project structure by name.

    Args:
        structure: The project structure
        folder_name: Name of the folder to find or None for root folder

    Returns:
        Optional[ProjectFolder]: The found folder or None
    """
    if not folder_name:
        return structure

    for folder in structure.folders:
        if folder.name == folder_name:
            return folder
    return None


def get_subfolder_by_name(
    parent_folder: ProjectFolder, subfolder_name: str
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


class ProjectLockUnavailableError(RuntimeError):
    """Raised when a project lock prevents execution."""

    pass


def with_lock_retry(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    async def wrapper(self: "StudioClient", *args, **kwargs):
        try:
            lock_info: LockInfo = await self._retrieve_lock()
            if lock_info is not None and lock_info.project_lock_key is not None:
                headers = kwargs.get("headers", {}) or {}
                headers[HEADER_SW_LOCK_KEY] = lock_info.project_lock_key
                kwargs["headers"] = headers

            return await func(self, *args, **kwargs)
        except EnrichedException as e:
            if e.status_code == 423:
                raise ProjectLockUnavailableError(
                    "Project is locked by another operation. Please try again later."
                ) from e
            raise

    return wrapper


class StudioSolutionsClient:
    def __init__(self, solution_id: str):
        from uipath import UiPath

        self.uipath: UiPath = UiPath()
        self._solutions_base_url: str = f"/studio_/backend/api/Solution/{solution_id}"

    @traced(name="create_project", run_type="uipath")
    async def create_project_async(
        self,
        project_name: str,
        project_type: str = "Agent",
        trigger_type: str = "Manual",
    ):
        """Create a new project in the specified solution.

        Args:
            project_name: The name for the new project
            project_type: The type of project to create (default: "Agent")
            trigger_type: The trigger type for the project (default: "Manual")

        Returns:
            dict: The created project details including project ID
        """
        data = {
            "createDefaultProjectCommand[projectType]": project_type,
            "createDefaultProjectCommand[triggerType]": trigger_type,
            "createDefaultProjectCommand[name]": project_name,
        }

        response = await self.uipath.api_client.request_async(
            "POST",
            url=f"{self._solutions_base_url}/projects",
            data=data,
            scoped="org",
        )

        return response.json()


class StudioClient:
    def __init__(self, project_id: str, uipath: Optional[UiPath] = None):
        self.uipath: UiPath = uipath or UiPath()
        self.file_operations_base_url: str = (
            f"/studio_/backend/api/Project/{project_id}/FileOperations"
        )
        self._lock_operations_base_url: str = (
            f"/studio_/backend/api/Project/{project_id}/Lock"
        )
        self._project_id = project_id
        self._solution_id_cache: Optional[str] = None
        self._resources_cache: Optional[List[dict[str, Any]]] = None

    async def _get_solution_id(self) -> str:
        # implement property cache logic as coroutines are not supported
        if self._solution_id_cache is not None:
            return self._solution_id_cache
        response = await self.uipath.api_client.request_async(
            "GET",
            url=f"/studio_/backend/api/Project/{self._project_id}",
            scoped="org",
        )
        self._solution_id_cache = response.json()["solutionId"]
        return self._solution_id_cache

    async def _get_existing_resources(self) -> List[dict[str, Any]]:
        if self._resources_cache is not None:
            return self._resources_cache

        solution_id = await self._get_solution_id()
        response = await self.uipath.api_client.request_async(
            "GET",
            url=f"/studio_/backend/api/resourcebuilder/solutions/{solution_id}/entities",
            scoped="org",
        )
        resources_data = response.json().get("resources", [])
        self._resources_cache = [
            {"name": r.get("name"), "kind": r.get("kind")} for r in resources_data
        ]
        return self._resources_cache

    async def get_resource_overwrites(self) -> dict[str, ResourceOverwrite]:
        """Get resource overwrites from the solution.

        Returns:
            dict[str, ResourceOverwrite]: Dict of resource overwrites
        """
        if not os.path.exists(UiPathConfig.bindings_file_path):
            return {}

        with open(UiPathConfig.bindings_file_path, "rb") as f:
            file_content = f.read()

        solution_id = await self._get_solution_id()
        tenant_id = os.getenv(ENV_TENANT_ID, None)

        files = [
            (
                "file",
                (
                    os.path.basename(UiPathConfig.bindings_file_path),
                    file_content,
                    "application/json",
                ),
            )
        ]

        response = await self.uipath.api_client.request_async(
            "POST",
            url=f"/studio_/backend/api/resourcebuilder/{solution_id}/binding-overwrites",
            scoped="org",
            headers={HEADER_TENANT_ID: tenant_id},
            files=files,
        )
        data = response.json()
        overwrites = {}

        for key, value in data.items():
            overwrites[key] = ResourceOverwriteParser.parse(key, value)

        return overwrites

    async def create_virtual_resource(
        self, virtual_resource_request: VirtualResourceRequest
    ) -> VirtualResourceResult:
        """Create a virtual resource or return appropriate status if it already exists.

        Args:
            virtual_resource_request: The virtual resource request details

        Returns:
            VirtualResourceResult: Result indicating the operation status and a formatted message
        """
        # Build base message with resource details
        base_message_parts = [
            f"Resource {click.style(virtual_resource_request.name, fg='cyan')}",
            f" (kind: {click.style(virtual_resource_request.kind, fg='yellow')}",
        ]

        if virtual_resource_request.type:
            base_message_parts.append(
                f", type: {click.style(virtual_resource_request.type, fg='yellow')}"
            )

        if virtual_resource_request.activity_name:
            base_message_parts.append(
                f", activity: {click.style(virtual_resource_request.activity_name, fg='yellow')}"
            )

        base_message_parts.append(")")
        base_message = "".join(base_message_parts)

        existing_resources = await self._get_existing_resources()

        # Check if resource with same kind and name exists
        existing_same_kind = next(
            (
                r
                for r in existing_resources
                if r["name"] == virtual_resource_request.name
                and r["kind"] == virtual_resource_request.kind
            ),
            None,
        )
        if existing_same_kind:
            message = f"{base_message} already exists. Skipping..."
            return VirtualResourceResult(severity=Severity.ATTENTION, message=message)

        # Check if resource with same name but different kind exists
        existing_diff_kind = next(
            (
                r
                for r in existing_resources
                if r["name"] == virtual_resource_request.name
                and r["kind"] != virtual_resource_request.kind
            ),
            None,
        )
        if existing_diff_kind:
            message = (
                f"Cannot create {base_message}. "
                f"A resource with this name already exists with kind {click.style(existing_diff_kind['kind'], fg='yellow')}. "
                f"Consider renaming the resource in code."
            )
            return VirtualResourceResult(severity=Severity.WARN, message=message)

        # Create the virtual resource
        solution_id = await self._get_solution_id()
        response = await self.uipath.api_client.request_async(
            "POST",
            url=f"/studio_/backend/api/resourcebuilder/solutions/{solution_id}/resources/virtual",
            scoped="org",
            json=virtual_resource_request.model_dump(exclude_none=True),
        )
        resource_key = response.json()["key"]
        await self._update_resource_specs(
            resource_key, new_specs={"name": virtual_resource_request.name}
        )

        # Update cache with newly created resource
        if self._resources_cache is not None:
            self._resources_cache.append(
                {
                    "name": virtual_resource_request.name,
                    "kind": virtual_resource_request.kind,
                }
            )

        message = f"{base_message} created successfully."
        return VirtualResourceResult(severity=Severity.SUCCESS, message=message)

    async def _update_resource_specs(
        self, resource_key: str, new_specs: dict[str, Any]
    ):
        solution_id = await self._get_solution_id()
        tenant_id = os.getenv(ENV_TENANT_ID, None)

        await self.uipath.api_client.request_async(
            "PATCH",
            url=f"/studio_/backend/api/resourcebuilder/solutions/{solution_id}/resources/{resource_key}/configuration",
            scoped="org",
            json=new_specs,
            headers={HEADER_TENANT_ID: tenant_id},
        )

    @traced(name="get_project_structure", run_type="uipath")
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

    @traced(name="create_folder", run_type="uipath")
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

    @traced(name="download_file", run_type="uipath")
    async def download_file_async(self, file_id: str) -> Any:
        response = await self.uipath.api_client.request_async(
            "GET",
            url=f"{self.file_operations_base_url}/File/{file_id}",
            scoped="org",
        )
        return response

    @traced(name="download_file", run_type="uipath")
    async def download_project_file_async(self, file: ProjectFile) -> Any:
        response = await self.uipath.api_client.request_async(
            "GET",
            url=f"{self.file_operations_base_url}/File/{file.id}",
            scoped="org",
        )
        return response

    @traced(name="upload_file", run_type="uipath")
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

    @traced(name="delete_file", run_type="uipath")
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

    @traced(name="synchronize_files", run_type="uipath")
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

    async def _put_lock(self):
        await self.uipath.api_client.request_async(
            "PUT",
            url=f"{self._lock_operations_base_url}/dummy-uuid-Shared?api-version=2",
            scoped="org",
        )
