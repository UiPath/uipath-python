from typing import Optional

from typing_extensions import deprecated

from ..._utils import Endpoint, RequestSpec
from ...tracing import traced
from ..common import BaseService, UiPathApiConfig, UiPathExecutionContext
from ..errors import FolderNotFoundException
from .folder import PersonalWorkspace


class FolderService(BaseService):
    """Service for managing UiPath Folders.

    A folder represents a single area for data organization
    and access control - it is created when you need to categorize, manage, and enforce authorization rules for a group
    of UiPath resources (i.e. processes, assets, connections, storage buckets etc.) or other folders
    """

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def retrieve_folder_key(self, folder_path: str | None) -> str | None:
        """Resolve a folder path to its corresponding folder key.

        Args:
            folder_path: Folder path to resolve to a key

        Returns:
            The resolved folder key

        Raises:
            ValueError: If folder_path is None or if folder_path is not found
        """
        if folder_path is None:
            raise ValueError("Cannot obtain folder_key without providing folder_path")

        resolved_folder_key = self.retrieve_key(folder_path=folder_path)
        if not resolved_folder_key:
            raise FolderNotFoundException(folder_path)
        return resolved_folder_key

    async def retrieve_folder_key_async(self, folder_path: str | None) -> str | None:
        """Asynchronously resolve a folder path to its corresponding folder key.

        Args:
            folder_path: Folder path to resolve to a key

        Returns:
            The resolved folder key

        Raises:
            ValueError: If folder_path is None or if folder_path is not found
        """
        if folder_path is None:
            raise ValueError("Cannot obtain folder_key without providing folder_path")

        resolved_folder_key = await self.retrieve_key_async(folder_path=folder_path)
        if not resolved_folder_key:
            raise FolderNotFoundException(folder_path)
        return resolved_folder_key

    @traced(name="folder_retrieve_key_by_folder_path", run_type="uipath")
    @deprecated("Use retrieve_key instead")
    def retrieve_key_by_folder_path(self, folder_path: str) -> Optional[str]:
        return self.retrieve_key(folder_path=folder_path)

    @traced(name="folder_retrieve_key", run_type="uipath")
    def retrieve_key(self, *, folder_path: str) -> Optional[str]:
        """Retrieve the folder key by folder path with pagination support.

        Args:
            folder_path: The fully qualified folder path to search for.

        Returns:
            The folder key if found, None otherwise.
        """
        skip = 0
        take = 20

        while True:
            spec = self._retrieve_spec(folder_path, skip=skip, take=take)
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            ).json()

            # Search for the folder in current page
            folder_key = next(
                (
                    item["Key"]
                    for item in response["PageItems"]
                    if item["FullyQualifiedName"] == folder_path
                ),
                None,
            )

            if folder_key is not None:
                return folder_key

            page_items = response["PageItems"]
            if len(page_items) < take:
                break

            skip += take

        return None

    @traced(name="folder_retrieve_key", run_type="uipath")
    async def retrieve_key_async(self, *, folder_path: str) -> Optional[str]:
        """Retrieve the folder key by folder path with pagination support.

        Args:
            folder_path: The fully qualified folder path to search for.

        Returns:
            The folder key if found, None otherwise.
        """
        skip = 0
        take = 20

        while True:
            spec = self._retrieve_spec(folder_path, skip=skip, take=take)
            response = (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                )
            ).json()

            # Search for the folder in current page
            folder_key = next(
                (
                    item["Key"]
                    for item in response["PageItems"]
                    if item["FullyQualifiedName"] == folder_path
                ),
                None,
            )

            if folder_key is not None:
                return folder_key

            page_items = response["PageItems"]
            if len(page_items) < take:
                break

            skip += take

        return None

    def _retrieve_spec(
        self, folder_path: str, *, skip: int = 0, take: int = 20
    ) -> RequestSpec:
        folder_name = folder_path.split("/")[-1]
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                "orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser"
            ),
            params={
                "searchText": folder_name,
                "skip": skip,
                "take": take,
            },
        )

    @traced(name="folder_get_personal_workspace", run_type="uipath")
    def get_personal_workspace(self) -> PersonalWorkspace:
        """Retrieve the personal workspace folder for the current user.

        Returns:
            PersonalWorkspace: The personal workspace information.

        Raises:
            ValueError: If the user does not have a personal workspace.
        """
        response = self.request(
            "GET",
            url=Endpoint(
                "orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended"
            ),
            params={"$select": "PersonalWorkspace", "$expand": "PersonalWorkspace"},
        ).json()

        personal_workspace = response.get("PersonalWorkspace")
        if personal_workspace is None:
            raise ValueError("Failed to fetch personal workspace")

        return PersonalWorkspace.model_validate(personal_workspace)

    @traced(name="folder_get_personal_workspace_async", run_type="uipath")
    async def get_personal_workspace_async(self) -> PersonalWorkspace:
        """Asynchronously retrieve the personal workspace folder for the current user.

        Returns:
            PersonalWorkspace: The personal workspace information.

        Raises:
            ValueError: If the personal workspace cannot be fetched.
        """
        response = (
            await self.request_async(
                "GET",
                url=Endpoint(
                    "orchestrator_/odata/Users/UiPath.Server.Configuration.OData.GetCurrentUserExtended"
                ),
                params={"$select": "PersonalWorkspace", "$expand": "PersonalWorkspace"},
            )
        ).json()

        personal_workspace = response.get("PersonalWorkspace")
        if personal_workspace is None:
            raise ValueError("Failed to fetch personal workspace")

        return PersonalWorkspace.model_validate(personal_workspace)
