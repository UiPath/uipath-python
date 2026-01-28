import json
import os
import uuid
from typing import Any, Dict, Optional

from ..._utils import Endpoint, RequestSpec, header_folder, resource_override
from ..._utils.constants import ENV_JOB_KEY, HEADER_JOB_KEY
from ...tracing import traced
from ..attachments import Attachment
from ..common import BaseService, FolderContext, UiPathApiConfig, UiPathExecutionContext
from ._attachments_service import AttachmentsService
from .job import Job


class ProcessesService(FolderContext, BaseService):
    """Service for managing and executing UiPath automation processes.

    Processes (also known as automations or workflows) are the core units of
    automation in UiPath, representing sequences of activities that perform
    specific business tasks.
    """

    _INPUT_ARGUMENTS_SIZE_LIMIT = 10000

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        attachment_service: AttachmentsService,
    ) -> None:
        self._attachments_service = attachment_service
        super().__init__(config=config, execution_context=execution_context)

    @resource_override(resource_type="process")
    @traced(name="processes_invoke", run_type="uipath")
    def invoke(
        self,
        name: str,
        input_arguments: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        attachments: Optional[list[Attachment]] = None,
    ) -> Job:
        """Start execution of a process by its name.

        Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

        Args:
            name (str): The name of the process to execute.
            input_arguments (Optional[Dict[str, Any]]): The input arguments to pass to the process.
            attachments (Optional[list]): List of Attachment objects to pass to the process.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Job: The job execution details.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()

            client.processes.invoke(name="MyProcess")
            ```

            ```python
            # if you want to execute the process in a specific folder
            # another one than the one set in the SDK config
            from uipath.platform import UiPath

            client = UiPath()

            client.processes.invoke(name="MyProcess", folder_path="my-folder-key")
            ```
        """
        input_data = self._handle_input_arguments(
            input_arguments=input_arguments,
            attachments=attachments,
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

    @resource_override(resource_type="process")
    @traced(name="processes_invoke", run_type="uipath")
    async def invoke_async(
        self,
        name: str,
        input_arguments: Optional[Dict[str, Any]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        attachments: Optional[list[Attachment]] = None,
    ) -> Job:
        """Asynchronously start execution of a process by its name.

        Related Activity: [Invoke Process](https://docs.uipath.com/activities/other/latest/workflow/invoke-process)

        Args:
            name (str): The name of the process to execute.
            input_arguments (Optional[Dict[str, Any]]): The input arguments to pass to the process.
            attachments (Optional[list]): List of Attachment objects to pass to the process.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.

        Returns:
            Job: The job execution details.

        Examples:
            ```python
            import asyncio

            from uipath.platform import UiPath

            sdk = UiPath()

            async def main():
                job = await sdk.processes.invoke_async("testAppAction")
                print(job)

            asyncio.run(main())
            ```
        """
        input_data = await self._handle_input_arguments_async(
            input_arguments=input_arguments,
            attachments=attachments,
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

    @staticmethod
    def _prepare_link_attachments(
        attachments: Optional[list[Attachment]],
    ) -> Optional[list[Dict[str, str]]]:
        """Format attachments for process invocation payload."""
        if not attachments:
            return None

        link_attachments = [
            {"attachmentId": str(att.id)} for att in attachments if att.id is not None
        ]
        return link_attachments if link_attachments else None

    def _handle_input_arguments(
        self,
        input_arguments: Optional[Dict[str, Any]] = None,
        attachments: Optional[list[Attachment]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle input arguments and attachments, storing as attachment if they exceed size limit.

        Args:
            input_arguments: The input arguments to process
            attachments: List of Attachment objects to pass to the process
            folder_key: The folder key for attachment storage
            folder_path: The folder path for attachment storage

        Returns:
            Dict containing either "InputArguments" or "InputFile" key, and optionally "Attachments"
        """
        result: Dict[str, Any] = {}

        # handle input arguments
        if not input_arguments:
            result["InputArguments"] = json.dumps({})
        else:
            # If payload exceeds limit, store as attachment
            payload_json = json.dumps(input_arguments)
            if len(payload_json) > self._INPUT_ARGUMENTS_SIZE_LIMIT:
                attachment_id = self._attachments_service.upload(
                    name=f"{uuid.uuid4()}.json",
                    content=payload_json,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )
                result["InputFile"] = str(attachment_id)
            else:
                result["InputArguments"] = payload_json

        link_attachments = self._prepare_link_attachments(attachments)
        if link_attachments:
            result["Attachments"] = link_attachments

        return result

    async def _handle_input_arguments_async(
        self,
        input_arguments: Optional[Dict[str, Any]] = None,
        attachments: Optional[list[Attachment]] = None,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle input arguments and attachments, storing as attachment if they exceed size limit.

        Args:
            input_arguments: The input arguments to process
            attachments: List of Attachment objects to pass to the process
            folder_key: The folder key for attachment storage
            folder_path: The folder path for attachment storage

        Returns:
            Dict containing either "InputArguments" or "InputFile" key, and optionally "Attachments"
        """
        result: Dict[str, Any] = {}

        if not input_arguments:
            result["InputArguments"] = json.dumps({})
        else:
            payload_json = json.dumps(input_arguments)
            if len(payload_json) > self._INPUT_ARGUMENTS_SIZE_LIMIT:
                attachment_id = await self._attachments_service.upload_async(
                    name=f"{uuid.uuid4()}.json",
                    content=payload_json,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )
                result["InputFile"] = str(attachment_id)
            else:
                result["InputArguments"] = payload_json

        formatted_attachments = self._prepare_link_attachments(attachments)
        if formatted_attachments:
            result["Attachments"] = formatted_attachments

        return result

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
