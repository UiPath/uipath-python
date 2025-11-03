import json
import os
import uuid
from typing import Any, Dict, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, resource_override
from .._utils.constants import ENV_JOB_KEY, HEADER_JOB_KEY
from ..models.job import Job
from ..tracing import traced
from . import AttachmentsService
from ._base_service import BaseService


class ProcessesService(FolderContext, BaseService):
    """Service for managing and executing UiPath automation processes.

    Processes (also known as automations or workflows) are the core units of
    automation in UiPath, representing sequences of activities that perform
    specific business tasks.
    """

    def __init__(
        self,
        config: Config,
        execution_context: ExecutionContext,
        attachment_service: AttachmentsService,
    ) -> None:
        self._attachments_service = attachment_service
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="processes_invoke", run_type="uipath")
    @resource_override(resource_type="process")
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
        input_data = self._handle_input_arguments(
            input_arguments=input_arguments,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        spec = self._invoke_spec(
            name,
            input_data=input_data,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )

        return Job.model_validate(response.json()["value"][0])

    @traced(name="processes_invoke", run_type="uipath")
    @resource_override(resource_type="process")
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
        input_data = await self._handle_input_arguments_async(
            input_arguments=input_arguments,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        spec = self._invoke_spec(
            name,
            input_data=input_data,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )

        return Job.model_validate(response.json()["value"][0])

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _handle_input_arguments(
        self,
        input_arguments: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, str]:
        """Handle input arguments, storing as attachment if they exceed size limit.

        Args:
            input_arguments: The input arguments to process
            folder_key: The folder key for attachment storage
            folder_path: The folder path for attachment storage

        Returns:
            Dict containing either "InputArguments" or "InputFile" key
        """
        if not input_arguments:
            return {"InputArguments": json.dumps({})}

        # If payload exceeds limit, store as attachment
        payload_json = json.dumps(input_arguments)
        if len(payload_json) > 10000:  # 10k char limit
            attachment_id = self._attachments_service.upload(
                name=f"{uuid.uuid4()}.json",
                content=payload_json,
                folder_key=folder_key,
                folder_path=folder_path,
            )
            return {"InputFile": str(attachment_id)}
        else:
            return {"InputArguments": payload_json}

    async def _handle_input_arguments_async(
        self,
        input_arguments: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, str]:
        """Handle input arguments, storing as attachment if they exceed size limit.

        Args:
            input_arguments: The input arguments to process
            folder_key: The folder key for attachment storage
            folder_path: The folder path for attachment storage

        Returns:
            Dict containing either "InputArguments" or "InputFile" key
        """
        if not input_arguments:
            return {"InputArguments": json.dumps({})}

        # If payload exceeds limit, store as attachment
        payload_json = json.dumps(input_arguments)
        if len(payload_json) > 10000:  # 10k char limit
            attachment_id = await self._attachments_service.upload_async(
                name=f"{uuid.uuid4()}.json",
                content=payload_json,
                folder_key=folder_key,
                folder_path=folder_path,
            )
            return {"InputFile": str(attachment_id)}
        else:
            return {"InputArguments": payload_json}

    def _invoke_spec(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        request_spec = RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
            ),
            json={"startInfo": {"ReleaseName": name, **(input_data or {})}},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
        job_key = os.environ.get(ENV_JOB_KEY, None)
        if job_key:
            request_spec.headers[HEADER_JOB_KEY] = job_key

        return request_spec
