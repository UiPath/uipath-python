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
from ..models.processes import Process
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

    @traced(name="processes_get_by_name", run_type="uipath")
    def get_by_name(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Process:
        """Get a release (process) by its exact name.

        Args:
            name (str): The exact name of the release to retrieve.
            folder_key (Optional[str]): The key of the folder to search in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to search in. Override the default one set in the SDK config.

        Returns:
            Process: The process (release) matching the name.

        Raises:
            ValueError: If the release is not found or multiple releases match.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            # Get a release by exact name
            release = client.processes.get_by_name("llamaindex-agent-no-llm")
            print(release.id)
            ```
        """
        spec = RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Releases"),
            params={
                "$filter": f"Name eq '{name}'",
                "$top": 2,  # Get 2 to detect if there are multiple matches
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        data = response.json()
        releases = data.get("value", [])

        if len(releases) == 0:
            raise ValueError(f"Release '{name}' not found")
        elif len(releases) > 1:
            raise ValueError(f"Multiple releases found with name '{name}'")

        return Process.model_validate(releases[0])

    @traced(name="processes_get_by_name", run_type="uipath")
    async def get_by_name_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Process:
        """Asynchronously get a release (process) by its exact name.

        Args:
            name (str): The exact name of the release to retrieve.
            folder_key (Optional[str]): The key of the folder to search in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to search in. Override the default one set in the SDK config.

        Returns:
            Process: The process (release) matching the name.

        Raises:
            ValueError: If the release is not found or multiple releases match.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            sdk = UiPath()

            async def main():
                release = await sdk.processes.get_by_name_async("llamaindex-agent-no-llm")
                print(release.id)

            asyncio.run(main())
            ```
        """
        spec = RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Releases"),
            params={
                "$filter": f"Name eq '{name}'",
                "$top": 2,  # Get 2 to detect if there are multiple matches
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        data = response.json()
        releases = data.get("value", [])

        if len(releases) == 0:
            raise ValueError(f"Release '{name}' not found")
        elif len(releases) > 1:
            raise ValueError(f"Multiple releases found with name '{name}'")

        return Process.model_validate(releases[0])

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

    @traced(name="processes_create_release", run_type="uipath")
    def create_release(
        self,
        name: str,
        process_key: str,
        process_version: str,
        entry_point_id: int,
        *,
        description: Optional[str] = None,
        environment_variables: Optional[str] = None,
        input_arguments: Optional[str] = None,
        specific_priority_value: Optional[int] = None,
        job_priority: Optional[str] = None,
        robot_size: Optional[str] = None,
        hidden_for_attended_user: bool = False,
        resource_overwrites: Optional[list] = None,
        remote_control_access: str = "None",
        retention_action: str = "Delete",
        retention_period: int = 20,
        stale_retention_action: str = "Delete",
        stale_retention_period: int = 30,
        tags: Optional[list] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Process:
        """Create a new release (process).

        Args:
            name (str): The name of the release.
            process_key (str): The process key.
            process_version (str): The process version.
            entry_point_id (int): The entry point ID.
            description (Optional[str]): The description of the release.
            environment_variables (Optional[str]): Environment variables as a string.
            input_arguments (Optional[str]): Input arguments as a JSON string.
            specific_priority_value (Optional[int]): Specific priority value.
            job_priority (Optional[str]): Job priority.
            robot_size (Optional[str]): Robot size.
            hidden_for_attended_user (bool): Whether hidden for attended user. Defaults to False.
            resource_overwrites (Optional[list]): Resource overwrites. Defaults to empty list.
            remote_control_access (str): Remote control access. Defaults to "None".
            retention_action (str): Retention action. Defaults to "Delete".
            retention_period (int): Retention period in days. Defaults to 20.
            stale_retention_action (str): Stale retention action. Defaults to "Delete".
            stale_retention_period (int): Stale retention period in days. Defaults to 30.
            tags (Optional[list]): Tags. Defaults to empty list.
            folder_key (Optional[str]): The key of the folder to create the release in.
            folder_path (Optional[str]): The path of the folder to create the release in.

        Returns:
            Process: The created release.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            release = client.processes.create_release(
                name="langchain-agent-no-llm",
                description="simple langchain agent with no llm",
                process_key="langchain-agent-no-llm",
                process_version="0.0.1",
                entry_point_id=596116,
                input_arguments="{}",
                specific_priority_value=45,
            )
            print(release.id)
            ```
        """
        spec = self._create_release_spec(
            name=name,
            process_key=process_key,
            process_version=process_version,
            entry_point_id=entry_point_id,
            description=description,
            environment_variables=environment_variables,
            input_arguments=input_arguments,
            specific_priority_value=specific_priority_value,
            job_priority=job_priority,
            robot_size=robot_size,
            hidden_for_attended_user=hidden_for_attended_user,
            resource_overwrites=resource_overwrites or [],
            remote_control_access=remote_control_access,
            retention_action=retention_action,
            retention_period=retention_period,
            stale_retention_action=stale_retention_action,
            stale_retention_period=stale_retention_period,
            tags=tags or [],
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return Process.model_validate(response.json())

    @traced(name="processes_create_release", run_type="uipath")
    async def create_release_async(
        self,
        name: str,
        process_key: str,
        process_version: str,
        entry_point_id: int,
        *,
        description: Optional[str] = None,
        environment_variables: Optional[str] = None,
        input_arguments: Optional[str] = None,
        specific_priority_value: Optional[int] = None,
        job_priority: Optional[str] = None,
        robot_size: Optional[str] = None,
        hidden_for_attended_user: bool = False,
        resource_overwrites: Optional[list] = None,
        remote_control_access: str = "None",
        retention_action: str = "Delete",
        retention_period: int = 20,
        stale_retention_action: str = "Delete",
        stale_retention_period: int = 30,
        tags: Optional[list] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Process:
        """Asynchronously create a new release (process).

        Args:
            name (str): The name of the release.
            process_key (str): The process key.
            process_version (str): The process version.
            entry_point_id (int): The entry point ID.
            description (Optional[str]): The description of the release.
            environment_variables (Optional[str]): Environment variables as a string.
            input_arguments (Optional[str]): Input arguments as a JSON string.
            specific_priority_value (Optional[int]): Specific priority value.
            job_priority (Optional[str]): Job priority.
            robot_size (Optional[str]): Robot size.
            hidden_for_attended_user (bool): Whether hidden for attended user. Defaults to False.
            resource_overwrites (Optional[list]): Resource overwrites. Defaults to empty list.
            remote_control_access (str): Remote control access. Defaults to "None".
            retention_action (str): Retention action. Defaults to "Delete".
            retention_period (int): Retention period in days. Defaults to 20.
            stale_retention_action (str): Stale retention action. Defaults to "Delete".
            stale_retention_period (int): Stale retention period in days. Defaults to 30.
            tags (Optional[list]): Tags. Defaults to empty list.
            folder_key (Optional[str]): The key of the folder to create the release in.
            folder_path (Optional[str]): The path of the folder to create the release in.

        Returns:
            Process: The created release.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            sdk = UiPath()

            async def main():
                release = await sdk.processes.create_release_async(
                    name="langchain-agent-no-llm",
                    description="simple langchain agent with no llm",
                    process_key="langchain-agent-no-llm",
                    process_version="0.0.1",
                    entry_point_id=596116,
                    input_arguments="{}",
                    specific_priority_value=45,
                )
                print(release.id)

            asyncio.run(main())
            ```
        """
        spec = self._create_release_spec(
            name=name,
            process_key=process_key,
            process_version=process_version,
            entry_point_id=entry_point_id,
            description=description,
            environment_variables=environment_variables,
            input_arguments=input_arguments,
            specific_priority_value=specific_priority_value,
            job_priority=job_priority,
            robot_size=robot_size,
            hidden_for_attended_user=hidden_for_attended_user,
            resource_overwrites=resource_overwrites or [],
            remote_control_access=remote_control_access,
            retention_action=retention_action,
            retention_period=retention_period,
            stale_retention_action=stale_retention_action,
            stale_retention_period=stale_retention_period,
            tags=tags or [],
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return Process.model_validate(response.json())

    def _create_release_spec(
        self,
        name: str,
        process_key: str,
        process_version: str,
        entry_point_id: int,
        description: Optional[str],
        environment_variables: Optional[str],
        input_arguments: Optional[str],
        specific_priority_value: Optional[int],
        job_priority: Optional[str],
        robot_size: Optional[str],
        hidden_for_attended_user: bool,
        resource_overwrites: list,
        remote_control_access: str,
        retention_action: str,
        retention_period: int,
        stale_retention_action: str,
        stale_retention_period: int,
        tags: list,
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        """Build request spec for creating a release."""
        body = {
            "Name": name,
            "ProcessKey": process_key,
            "ProcessVersion": process_version,
            "EntryPointId": entry_point_id,
            "EnvironmentVariables": environment_variables or "",
            "InputArguments": input_arguments or "{}",
            "HiddenForAttendedUser": hidden_for_attended_user,
            "ResourceOverwrites": resource_overwrites,
            "RemoteControlAccess": remote_control_access,
            "RetentionAction": retention_action,
            "RetentionPeriod": retention_period,
            "StaleRetentionAction": stale_retention_action,
            "StaleRetentionPeriod": stale_retention_period,
            "Tags": tags,
        }

        # Add optional fields only if provided
        if description is not None:
            body["Description"] = description
        if specific_priority_value is not None:
            body["SpecificPriorityValue"] = specific_priority_value
        if job_priority is not None:
            body["JobPriority"] = job_priority
        if robot_size is not None:
            body["RobotSize"] = robot_size

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.CreateRelease"
            ),
            json=body,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

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
