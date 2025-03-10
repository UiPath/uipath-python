from typing import Dict, Optional

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Process
from .._utils import Endpoint, RequestSpec, header_folder
from ._base_service import BaseService


class ProcessesService(FolderContext, BaseService):
    """
    Service for managing and executing UiPath automation processes.

    Processes (also known as automations or workflows) are the core units of
    automation in UiPath, representing sequences of activities that perform
    specific business tasks.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def invoke(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """
        Start execution of a process by its name.

        Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

        Args:
            name (str): The name of the process to execute.

        Returns:
            Response: The HTTP response containing the job execution details.

        Raises:
            Exception: If the process with the given name is not found.
        """
        process = self.retrieve(name, folder_key=folder_key, folder_path=folder_path)
        process_key = process.Key

        spec = self._invoke_spec(
            process_key, folder_key=folder_key, folder_path=folder_path
        )

        return self.request(spec.method, url=spec.endpoint, content=spec.content)

    async def invoke_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Response:
        """
        Asynchronously start execution of a process by its name.

        Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

        Args:
            name (str): The name of the process to execute.

        Returns:
            Response: The HTTP response containing the job execution details.

        Raises:
            Exception: If the process with the given name is not found.
        """
        process = await self.retrieve_async(
            name, folder_key=folder_key, folder_path=folder_path
        )
        process_key = process.Key

        spec = self._invoke_spec(
            process_key, folder_key=folder_key, folder_path=folder_path
        )

        return await self.request_async(
            spec.method, url=spec.endpoint, content=spec.content, headers=spec.headers
        )

    def retrieve(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Process:
        """
        Retrieve process details by its name.

        Args:
            name (str): The name of the process to retrieve.

        Returns:
            Process: The process details.

        Raises:
            Exception: If the process with the given name is not found.
        """
        spec = self._retrieve_spec(name, folder_key=folder_key, folder_path=folder_path)

        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        except Exception as e:
            raise Exception(f"Process with name {name} not found") from e

        return Process.model_validate(response.json()["value"][0])

    async def retrieve_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Process:
        """
        Asynchronously retrieve process details by its name.

        Args:
            name (str): The name of the process to retrieve.

        Returns:
            Process: The process details.

        Raises:
            Exception: If the process with the given name is not found.
        """
        spec = self._retrieve_spec(name, folder_key=folder_key, folder_path=folder_path)

        try:
            response = await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        except Exception as e:
            raise Exception(f"Process with name {name} not found") from e

        return Process.model_validate(response.json()["value"][0])

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _invoke_spec(
        self,
        process_key: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
            ),
            content=str({"startInfo": {"ReleaseKey": process_key}}),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_spec(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                "/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases"
            ),
            params={"$filter": f"Name eq '{name}'", "$top": 1},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
