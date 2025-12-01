import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, resource_override
from .._utils.constants import (
    ENV_TENANT_ID,
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
    HEADER_TENANT_ID,
)
from ..platform.action_center import Task, TaskSchema
from ..tracing import traced
from ._base_service import BaseService


def _create_spec(
    data: Optional[Dict[str, Any]],
    action_schema: Optional[TaskSchema],
    title: str,
    app_key: Optional[str] = None,
    app_folder_key: Optional[str] = None,
    app_folder_path: Optional[str] = None,
    app_version: Optional[int] = None,
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    is_actionable_message_enabled: Optional[bool] = None,
    actionable_message_metadata: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    job_key: Optional[str] = None,
    process_key: Optional[str] = None,
    resource_key: Optional[str] = None,
) -> RequestSpec:
    field_list = []
    outcome_list = []
    if action_schema:
        if action_schema.inputs:
            for input_field in action_schema.inputs:
                field_name = input_field.name
                field_list.append(
                    {
                        "Id": input_field.key,
                        "Name": field_name,
                        "Title": field_name,
                        "Type": "Fact",
                        "Value": data.get(field_name, "") if data is not None else "",
                    }
                )
        if action_schema.outputs:
            for output_field in action_schema.outputs:
                field_name = output_field.name
                field_list.append(
                    {
                        "Id": output_field.key,
                        "Name": field_name,
                        "Title": field_name,
                        "Type": "Fact",
                        "Value": "",
                    }
                )
        if action_schema.in_outs:
            for inout_field in action_schema.in_outs:
                field_name = inout_field.name
                field_list.append(
                    {
                        "Id": inout_field.key,
                        "Name": field_name,
                        "Title": field_name,
                        "Type": "Fact",
                        "Value": data.get(field_name, "") if data is not None else "",
                    }
                )
        if action_schema.outcomes:
            for outcome in action_schema.outcomes:
                outcome_list.append(
                    {
                        "Id": action_schema.key,
                        "Name": outcome.name,
                        "Title": outcome.name,
                        "Type": "Action.Http",
                        "IsPrimary": True,
                    }
                )

    # Build tags array from labels
    tags = []
    if labels:
        for label in labels:
            tags.append(
                {
                    "Name": label,
                    "DisplayName": label,
                    "Value": label,
                    "DisplayValue": label,
                }
            )

    # Build additional properties
    additional_properties: Dict[str, Any] = {}
    if resource_key:
        additional_properties["AppType"] = "Dynamic"
        additional_properties["FolderKey"] = app_folder_key or ""

    # Build task source metadata
    task_source_metadata: Dict[str, Any] = {}
    if instance_id:
        task_source_metadata["InstanceId"] = instance_id
    if app_folder_key:
        task_source_metadata["FolderKey"] = app_folder_key
    if job_key:
        task_source_metadata["JobKey"] = job_key
    if process_key:
        task_source_metadata["ProcessKey"] = process_key

    # Build task source
    task_source: Optional[Dict[str, Any]] = None
    if agent_id:
        task_source = {
            "SourceName": "Agent",
            "SourceId": agent_id,
            "TaskSourceMetadata": task_source_metadata,
        }

    # Build base payload matching .NET structure
    payload: Dict[str, Any] = {
        "appId": app_key,
        "title": title,
        "data": data if data is not None else {},
    }

    # Add optional fields
    if app_version is not None:
        payload["appVersion"] = app_version
    if priority is not None:
        payload["priority"] = priority
    if tags:
        payload["tags"] = tags
    if is_actionable_message_enabled is not None:
        payload["isActionableMessageEnabled"] = is_actionable_message_enabled
    if additional_properties:
        payload["additionalProperties"] = additional_properties
    if task_source:
        payload["taskSource"] = task_source

    # Add actionable message metadata (legacy format for backward compatibility)
    if actionable_message_metadata:
        payload["actionableMessageMetaData"] = actionable_message_metadata
    elif action_schema is not None:
        payload["actionableMessageMetaData"] = {
            "fieldSet": {
                "id": str(uuid.uuid4()),
                "fields": field_list,
            }
            if len(field_list) != 0
            else {},
            "actionSet": {
                "id": str(uuid.uuid4()),
                "actions": outcome_list,
            }
            if len(outcome_list) != 0
            else {},
        }

    return RequestSpec(
        method="POST",
        endpoint=Endpoint("/orchestrator_/tasks/AppTasks/CreateAppTask"),
        json=payload,
        headers=folder_headers(app_folder_key, app_folder_path),
    )


def _retrieve_action_spec(
    action_key: str, app_folder_key: str, app_folder_path: str
) -> RequestSpec:
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/orchestrator_/tasks/GenericTasks/GetTaskDataByKey"),
        params={"taskKey": action_key},
        headers=folder_headers(app_folder_key, app_folder_path),
    )


def _assign_task_spec(task_key: str, assignee: str) -> RequestSpec:
    return RequestSpec(
        method="POST",
        endpoint=Endpoint(
            "/orchestrator_/odata/Tasks/UiPath.Server.Configuration.OData.AssignTasks"
        ),
        json={"taskAssignments": [{"taskId": task_key, "UserNameOrEmail": assignee}]},
    )


def _retrieve_app_key_spec(app_name: str) -> RequestSpec:
    tenant_id = os.getenv(ENV_TENANT_ID, None)
    if not tenant_id:
        raise Exception(f"{ENV_TENANT_ID} env var is not set")
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/apps_/default/api/v1/default/deployed-action-apps-schemas"),
        params={
            "search": app_name,
            "filterByDeploymentTitle": "true",
            "state": "deployed",
        },
        headers={HEADER_TENANT_ID: tenant_id},
    )


def folder_headers(
    app_folder_key: Optional[str], app_folder_path: Optional[str]
) -> Dict[str, str]:
    headers = {}
    if app_folder_key:
        headers[HEADER_FOLDER_KEY] = app_folder_key
    elif app_folder_path:
        headers[HEADER_FOLDER_PATH] = app_folder_path
    return headers


class TasksService(FolderContext, BaseService):
    """Service for managing UiPath Action Center tasks.

    Tasks are task-based automation components that can be integrated into
    applications and processes. They represent discrete units of work that can
    be triggered and monitored through the UiPath API.

    This service provides methods to create and retrieve tasks, supporting
    both app-specific and generic tasks. It inherits folder context management
    capabilities from FolderContext.

    Reference: https://docs.uipath.com/automation-cloud/docs/actions
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="tasks_create", run_type="uipath")
    @resource_override(
        resource_type="app",
        resource_identifier="app_name",
        folder_identifier="app_folder_path",
    )
    async def create_async(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_name: Optional[str] = None,
        app_key: Optional[str] = None,
        app_folder_path: Optional[str] = None,
        app_folder_key: Optional[str] = None,
        assignee: Optional[str] = None,
        app_version: Optional[int] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        is_actionable_message_enabled: Optional[bool] = None,
        actionable_message_metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        job_key: Optional[str] = None,
        process_key: Optional[str] = None,
        resource_key: Optional[str] = None,
    ) -> Task:
        """Creates a new action asynchronously.

        This method creates a new action task in UiPath Orchestrator. The action can be
        either app-specific (using app_name or app_key) or a generic action.

        Args:
            title: The title of the action
            data: Optional dictionary containing input data for the action
            app_name: The name of the application (if creating an app-specific action)
            app_key: The key of the application (if creating an app-specific action)
            app_folder_path: Optional folder path for the action
            app_folder_key: Optional folder key for the action
            assignee: Optional username or email to assign the task to
            app_version: Optional application version
            priority: Optional task priority (Low, Medium, High, Critical)
            labels: Optional list of tag labels for the task
            is_actionable_message_enabled: Optional flag for actionable message feature
            actionable_message_metadata: Optional metadata for actionable messages
            agent_id: Optional agent identifier for task source
            instance_id: Optional instance/trace identifier
            job_key: Optional job key for task source metadata
            process_key: Optional process key for task source metadata
            resource_key: Optional resource key for additional properties

        Returns:
            Action: The created action object

        Raises:
            Exception: If neither app_name nor app_key is provided for app-specific actions
        """
        app_folder_path = app_folder_path if app_folder_path else self._folder_path

        (key, action_schema) = (
            (app_key, None)
            if app_key
            else await self._get_app_key_and_schema_async(app_name, app_folder_path)
        )
        spec = _create_spec(
            title=title,
            data=data,
            app_key=key,
            action_schema=action_schema,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
            app_version=app_version,
            priority=priority,
            labels=labels,
            is_actionable_message_enabled=is_actionable_message_enabled,
            actionable_message_metadata=actionable_message_metadata,
            agent_id=agent_id,
            instance_id=instance_id,
            job_key=job_key,
            process_key=process_key,
            resource_key=resource_key,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        json_response = response.json()
        if assignee:
            spec = _assign_task_spec(json_response["id"], assignee)
            await self.request_async(
                spec.method, spec.endpoint, json=spec.json, content=spec.content
            )
        return Task.model_validate(json_response)

    @traced(name="tasks_create", run_type="uipath")
    @resource_override(
        resource_type="app",
        resource_identifier="app_name",
        folder_identifier="app_folder_path",
    )
    def create(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_name: Optional[str] = None,
        app_key: Optional[str] = None,
        app_folder_path: Optional[str] = None,
        app_folder_key: Optional[str] = None,
        assignee: Optional[str] = None,
        app_version: Optional[int] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        is_actionable_message_enabled: Optional[bool] = None,
        actionable_message_metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        job_key: Optional[str] = None,
        process_key: Optional[str] = None,
        resource_key: Optional[str] = None,
    ) -> Task:
        """Creates a new task synchronously.

        This method creates a new action task in UiPath Orchestrator. The action can be
        either app-specific (using app_name or app_key) or a generic action.

        Args:
            title: The title of the action
            data: Optional dictionary containing input data for the action
            app_name: The name of the application (if creating an app-specific action)
            app_key: The key of the application (if creating an app-specific action)
            app_folder_path: Optional folder path for the action
            app_folder_key: Optional folder key for the action
            assignee: Optional username or email to assign the task to
            app_version: Optional application version
            priority: Optional task priority (Low, Medium, High, Critical)
            labels: Optional list of tag labels for the task
            is_actionable_message_enabled: Optional flag for actionable message feature
            actionable_message_metadata: Optional metadata for actionable messages
            agent_id: Optional agent identifier for task source
            instance_id: Optional instance/trace identifier
            job_key: Optional job key for task source metadata
            process_key: Optional process key for task source metadata
            resource_key: Optional resource key for additional properties

        Returns:
            Action: The created action object

        Raises:
            Exception: If neither app_name nor app_key is provided for app-specific actions
        """
        app_folder_path = app_folder_path if app_folder_path else self._folder_path

        (key, action_schema) = (
            (app_key, None)
            if app_key
            else self._get_app_key_and_schema(app_name, app_folder_path)
        )
        spec = _create_spec(
            title=title,
            data=data,
            app_key=key,
            action_schema=action_schema,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
            app_version=app_version,
            priority=priority,
            labels=labels,
            is_actionable_message_enabled=is_actionable_message_enabled,
            actionable_message_metadata=actionable_message_metadata,
            agent_id=agent_id,
            instance_id=instance_id,
            job_key=job_key,
            process_key=process_key,
            resource_key=resource_key,
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        json_response = response.json()
        if assignee:
            spec = _assign_task_spec(json_response["id"], assignee)
            self.request(
                spec.method, spec.endpoint, json=spec.json, content=spec.content
            )
        return Task.model_validate(json_response)

    @traced(name="tasks_retrieve", run_type="uipath")
    def retrieve(
        self, action_key: str, app_folder_path: str = "", app_folder_key: str = ""
    ) -> Task:
        """Retrieves a task by its key synchronously.

        Args:
            action_key: The unique identifier of the task to retrieve
            app_folder_path: Optional folder path for the task
            app_folder_key: Optional folder key for the task

        Returns:
            Task: The retrieved task object
        """
        spec = _retrieve_action_spec(
            action_key=action_key,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
        )
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )

        return Task.model_validate(response.json())

    @traced(name="tasks_retrieve", run_type="uipath")
    async def retrieve_async(
        self, action_key: str, app_folder_path: str = "", app_folder_key: str = ""
    ) -> Task:
        """Retrieves a task by its key asynchronously.

        Args:
            action_key: The unique identifier of the task to retrieve
            app_folder_path: Optional folder path for the task
            app_folder_key: Optional folder key for the task

        Returns:
            Task: The retrieved task object
        """
        spec = _retrieve_action_spec(
            action_key=action_key,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )

        return Task.model_validate(response.json())

    async def _get_app_key_and_schema_async(
        self, app_name: Optional[str], app_folder_path: Optional[str]
    ) -> Tuple[str, Optional[TaskSchema]]:
        if not app_name:
            raise Exception("appName or appKey is required")
        spec = _retrieve_app_key_spec(app_name=app_name)

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
            scoped="org",
        )
        try:
            deployed_app = self._extract_deployed_app(
                response.json()["deployed"], app_folder_path
            )
            action_schema = deployed_app["actionSchema"]
            deployed_app_key = deployed_app["systemName"]
        except (KeyError, IndexError):
            raise Exception("Action app not found") from None
        try:
            return (
                deployed_app_key,
                TaskSchema(
                    key=action_schema["key"],
                    in_outs=action_schema["inOuts"],
                    inputs=action_schema["inputs"],
                    outputs=action_schema["outputs"],
                    outcomes=action_schema["outcomes"],
                ),
            )
        except KeyError:
            raise Exception("Failed to deserialize action schema") from KeyError

    def _get_app_key_and_schema(
        self, app_name: Optional[str], app_folder_path: Optional[str]
    ) -> Tuple[str, Optional[TaskSchema]]:
        if not app_name:
            raise Exception("appName or appKey is required")

        spec = _retrieve_app_key_spec(app_name=app_name)

        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
            scoped="org",
        )

        try:
            deployed_app = self._extract_deployed_app(
                response.json()["deployed"], app_folder_path
            )
            action_schema = deployed_app["actionSchema"]
            deployed_app_key = deployed_app["systemName"]
        except (KeyError, IndexError):
            raise Exception("Action app not found") from None
        try:
            return (
                deployed_app_key,
                TaskSchema(
                    key=action_schema["key"],
                    in_outs=action_schema["inOuts"],
                    inputs=action_schema["inputs"],
                    outputs=action_schema["outputs"],
                    outcomes=action_schema["outcomes"],
                ),
            )
        except KeyError:
            raise Exception("Failed to deserialize action schema") from KeyError

    # should be removed after folder filtering support is added on apps API
    def _extract_deployed_app(
        self, deployed_apps: List[Dict[str, Any]], app_folder_path: Optional[str]
    ) -> Dict[str, Any]:
        if len(deployed_apps) > 1 and not app_folder_path:
            raise Exception("Multiple app schemas found")
        try:
            if app_folder_path:
                return next(
                    app
                    for app in deployed_apps
                    if app["deploymentFolder"]["fullyQualifiedName"] == app_folder_path
                )
            else:
                return next(
                    app
                    for app in deployed_apps
                    if app["deploymentFolder"]["key"] == self._folder_key
                )
        except StopIteration:
            raise KeyError from StopIteration

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
