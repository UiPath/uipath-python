from typing import Any, List, Optional, Union

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator


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
        id: The unique identifier of the folder
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

    id: str = Field(alias="id")
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


class ProjectStructure(BaseModel):
    """Model representing the complete file structure of a UiPath project.

    Attributes:
        id: The unique identifier of the root folder (optional)
        name: The name of the root folder (optional)
        folders: List of folders in the project
        files: List of files at the root level
        folder_type: The type of the root folder (optional)
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    id: Optional[str] = Field(default=None, alias="id")
    name: Optional[str] = Field(default=None, alias="name")
    folders: List[ProjectFolder] = Field(default_factory=list)
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
    headers = {"Authorization": f"Bearer {token}"}
    url = (
        f"{base_url}/studio_/backend/api/Project/{project_id}/FileOperations/Structure"
    )

    response = client.get(url, headers=headers)
    response.raise_for_status()
    return ProjectStructure.model_validate(response.json())


def download_file(base_url: str, file_id: str, client: httpx.Client, token: str) -> Any:
    file_url = f"{base_url}/File/{file_id}"
    response = client.get(file_url, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response


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
