import json
import os
from typing import Any, Dict, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, infer_bindings
from .._utils.constants import ENV_JOB_ID, HEADER_JOB_KEY
from ..models.job import Job
from ..tracing._traced import traced
from ._base_service import BaseService


class ProcessesService(FolderContext, BaseService):
    """Service for managing and executing UiPath automation processes.

    Processes (also known as automations or workflows) are the core units of
    automation in UiPath, representing sequences of activities that perform
    specific business tasks.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="processes_invoke", run_type="uipath")
    def invoke(
        self,
        name: str,
        input_arguments: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Job:
        """Start execution of a process by its name.

        Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

        Args:
            name (str): The name of the process to execute.
            input_arguments (Optional[Dict[str, Any]]): The input arguments to pass to the process.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Job: The job execution details.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            client.processes.invoke(name="MyProcess")
            ```

            ```python
            # if you want to execute the process in a specific folder
            # another one than the one set in the SDK config
            from uipath import UiPath

            client = UiPath()

            client.processes.invoke(name="MyProcess", folder_path="my-folder-key")
            ```
        """
        spec = self._invoke_spec(
            name,
            input_arguments=input_arguments,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        return Job.model_validate(response.json()["value"][0])

    @infer_bindings()
    @traced(name="processes_invoke", run_type="uipath")
    async def invoke_async(
        self,
        name: str,
        input_arguments: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Job:
        """Asynchronously start execution of a process by its name.

        Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

        Args:
            name (str): The name of the process to execute.
            input_arguments (Optional[Dict[str, Any]]): The input arguments to pass to the process.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Job: The job execution details.

        Examples:
            ```python
            import asyncio

            from uipath import UiPath

            sdk = UiPath()

            async def main():
                job = await sdk.processes.invoke_async("testAppAction")
                print(job)

            asyncio.run(main())
            ```
        """
        spec = self._invoke_spec(
            name,
            input_arguments=input_arguments,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        return Job.model_validate(response.json()["value"][0])

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _invoke_spec(
        self,
        name: str,
        input_arguments: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        request_scope = RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
            ),
            content=str(
                {
                    "startInfo": {
                        "ReleaseName": name,
                        "InputArguments": json.dumps(input_arguments)
                        if input_arguments
                        else "{}",
                    }
                }
            ),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
        job_key = os.environ.get(ENV_JOB_ID, None)
        if job_key:
            request_scope.headers[HEADER_JOB_KEY] = job_key
        return request_scope
