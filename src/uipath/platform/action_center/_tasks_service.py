import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..._utils import Endpoint, RequestSpec, resource_override
from ..._utils.constants import (
    ENV_TENANT_ID,
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
    HEADER_TENANT_ID,
)
from ...tracing import traced
from ..common import (
    BaseService,
    FolderContext,
    UiPathApiConfig,
    UiPathConfig,
    UiPathExecutionContext,
)
from .task_schema import TaskSchema
from .tasks import Task, TaskRecipient, TaskRecipientType


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

    json_payload = {
        "appId": app_key,
        "title": title,
        "data": data if data is not None else {},
        "actionableMessageMetaData": actionable_message_metadata
        if actionable_message_metadata is not None
        else (
            {
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
            if action_schema is not None
            else {}
        ),
    }

    if app_version is not None:
        json_payload["appVersion"] = app_version
    if priority is not None:
        json_payload["priority"] = _normalize_priority(priority)
    if labels is not None:
        json_payload["tags"] = [
            {
                "name": label,
                "displayName": label,
                "value": label,
                "displayValue": label,
            }
            for label in labels
        ]
    if is_actionable_message_enabled is not None:
        json_payload["isActionableMessageEnabled"] = is_actionable_message_enabled

    return RequestSpec(
        method="POST",
        endpoint=Endpoint("/orchestrator_/tasks/AppTasks/CreateAppTask"),
        json=json_payload,
        headers=folder_headers(app_folder_key, app_folder_path),
    )


def _normalize_priority(priority: str | None) -> str | None:
    """Normalize priority string to match API expectations.

    Converts case-insensitive priority strings to the proper capitalized format
    expected by the Orchestrator API.

    Args:
        priority: Priority string (case-insensitive: "low", "HIGH", "MeDiUm", etc.)

    Returns:
        Normalized priority string ("Low", "Medium", "High", "Critical") or None
    """
    if priority is None or not priority.strip():
        return None

    priority_map = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
    }

    normalized = priority_map.get(priority.lower())
    if normalized is None:
        raise ValueError(
            f"Invalid priority value: '{priority}'. "
            f"Must be one of: Low, Medium, High, Critical (case-insensitive)"
        )

    return normalized


def _retrieve_action_spec(
    action_key: str, app_folder_key: str, app_folder_path: str
) -> RequestSpec:
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/orchestrator_/tasks/GenericTasks/GetTaskDataByKey"),
        params={"taskKey": action_key},
        headers=folder_headers(app_folder_key, app_folder_path),
    )


async def _assign_task_spec(
    self, task_key: str, assignee: str | None, task_recipient: TaskRecipient | None
) -> RequestSpec:
    request_spec = RequestSpec(
        method="POST",
        endpoint=Endpoint(
            "/orchestrator_/odata/Tasks/UiPath.Server.Configuration.OData.AssignTasks"
        ),
    )
    if task_recipient:
        recipient_value = await _resolve_recipient(self, task_recipient)
        if (
            task_recipient.type == TaskRecipientType.USER_ID
            or task_recipient.type == TaskRecipientType.EMAIL
        ):
            request_spec.json = {
                "taskAssignments": [
                    {
                        "taskId": task_key,
                        "assignmentCriteria": "SingleUser",
                        "userNameOrEmail": recipient_value,
                    }
                ]
            }
        else:
            request_spec.json = {
                "taskAssignments": [
                    {
                        "taskId": task_key,
                        "assignmentCriteria": "AllUsers",
                        "assigneeNamesOrEmails": [recipient_value],
                    }
                ]
            }
    elif assignee:
        request_spec.json = {
            "taskAssignments": [{"taskId": task_key, "UserNameOrEmail": assignee}]
        }
    return request_spec


async def _resolve_recipient(self, task_recipient: TaskRecipient) -> str:
    recipient_value = task_recipient.value
    if task_recipient.type == TaskRecipientType.USER_ID:
        user_spec = _resolve_user(task_recipient.value)
        user_response = await self.request_async(
            user_spec.method,
            user_spec.endpoint,
            json=user_spec.json,
            content=user_spec.content,
            headers=user_spec.headers,
            scoped="org",
        )
        recipient_value = user_response.json().get("email")
    if task_recipient.type == TaskRecipientType.GROUP_ID:
        group_spec = _resolve_group(task_recipient.value)
        group_response = await self.request_async(
            group_spec.method,
            group_spec.endpoint,
            json=group_spec.json,
            content=group_spec.content,
            headers=group_spec.headers,
            scoped="org",
        )
        recipient_value = group_response.json().get("displayName")
    return recipient_value


def _resolve_user(entity_id: str) -> RequestSpec:
    org_id = UiPathConfig.organization_id
    return RequestSpec(
        method="POST",
        endpoint=Endpoint(
            "/identity_/api/Directory/Resolve/{org_id}".format(org_id=org_id)
        ),
        json={"entityId": entity_id, "entityType": "User"},
    )


def _resolve_group(entity_id: str) -> RequestSpec:
    org_id = UiPathConfig.organization_id
    return RequestSpec(
        method="GET",
        endpoint=Endpoint(
            "/identity_/api/Group/{org_id}/{entity_id}".format(
                org_id=org_id, entity_id=entity_id
            )
        ),
    )


def _retrieve_app_key_spec(app_name: str) -> RequestSpec:
    tenant_id = os.getenv(ENV_TENANT_ID, None)
    if not tenant_id:
        raise Exception(f"{ENV_TENANT_ID} env var is not set")
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/apps_/default/api/v1/default/deployed-action-apps-schemas"),
        params={"search": app_name, "filterByDeploymentTitle": "true"},
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

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @resource_override(
        resource_type="app",
        resource_identifier="app_name",
        folder_identifier="app_folder_path",
    )
    @traced(name="tasks_create", run_type="uipath")
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
        recipient: Optional[TaskRecipient] = None,
        app_version: Optional[int] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        is_actionable_message_enabled: Optional[bool] = None,
        actionable_message_metadata: Optional[Dict[str, Any]] = None,
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
            app_version: Optional version of the app
            priority: Optional priority of the task
            labels: Optional list of labels for the task
            is_actionable_message_enabled: Optional boolean indicating <?>
            actionable_message_metadata: Optional metadata for the action

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
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        json_response = response.json()
        if assignee or recipient:
            spec = await _assign_task_spec(
                self, json_response["id"], assignee, recipient
            )
            await self.request_async(
                spec.method, spec.endpoint, json=spec.json, content=spec.content
            )
        return Task.model_validate(json_response)

    @resource_override(
        resource_type="app",
        resource_identifier="app_name",
        folder_identifier="app_folder_path",
    )
    @traced(name="tasks_create", run_type="uipath")
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
        recipient: Optional[TaskRecipient] = None,
        app_version: Optional[int] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        is_actionable_message_enabled: Optional[bool] = None,
        actionable_message_metadata: Optional[Dict[str, Any]] = None,
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
            app_version: Optional version of the app
            priority: Optional priority of the task
            labels: Optional list of labels for the task
            is_actionable_message_enabled: Optional boolean indicating <?>
            actionable_message_metadata: Optional metadata for the action

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
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            content=spec.content,
            headers=spec.headers,
        )
        json_response = response.json()
        if assignee or recipient:
            spec = asyncio.run(
                _assign_task_spec(self, json_response["id"], assignee, recipient)
            )
            self.request(
                spec.method, spec.endpoint, json=spec.json, content=spec.content
            )
        return Task.model_validate(json_response)

    @resource_override(
        resource_type="app",
        resource_identifier="app_name",
        folder_identifier="app_folder_path",
    )
    @traced(name="tasks_retrieve", run_type="uipath")
    def retrieve(
        self,
        action_key: str,
        app_folder_path: str = "",
        app_folder_key: str = "",
        app_name: str | None = None,
    ) -> Task:
        """Retrieves a task by its key synchronously.

        Args:
            action_key: The unique identifier of the task to retrieve
            app_folder_path: Optional folder path for the task
            app_folder_key: Optional folder key for the task
            app_name: app name hint for resource override
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

    @resource_override(
        resource_type="app",
        resource_identifier="app_name",
        folder_identifier="app_folder_path",
    )
    @traced(name="tasks_retrieve", run_type="uipath")
    async def retrieve_async(
        self,
        action_key: str,
        app_folder_path: str = "",
        app_folder_key: str = "",
        app_name: str | None = None,
    ) -> Task:
        """Retrieves a task by its key asynchronously.

        Args:
            action_key: The unique identifier of the task to retrieve
            app_folder_path: Optional folder path for the task
            app_folder_key: Optional folder key for the task
            app_name: app name hint for resource override
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
