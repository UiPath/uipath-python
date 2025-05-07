import os
import uuid
from json import dumps
from typing import Any, Dict, List, Optional, Tuple

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec
from .._utils.constants import (
    ENV_TENANT_ID,
    HEADER_FOLDER_KEY,
    HEADER_FOLDER_PATH,
    HEADER_TENANT_ID,
)
from ..models import Action, ActionSchema
from ..tracing._traced import traced
from ._base_service import BaseService


def _create_spec(
    data: Optional[Dict[str, Any]],
    action_schema: Optional[ActionSchema],
    title: str,
    app_key: Optional[str] = None,
    app_version: Optional[int] = 1,
    app_folder_key: Optional[str] = None,
    app_folder_path: Optional[str] = None,
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

    return RequestSpec(
        method="POST",
        endpoint=Endpoint("/orchestrator_/tasks/AppTasks/CreateAppTask"),
        content=dumps(
            {
                "appId": app_key,
                "appVersion": app_version,
                "title": title,
                "data": data if data is not None else {},
                "actionableMessageMetaData": {
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
                else {},
            }
        ),
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
        content=dumps(
            {"taskAssignments": [{"taskId": task_key, "UserNameOrEmail": assignee}]}
        ),
    )


def _retrieve_app_key_spec(app_name: str) -> RequestSpec:
    tenant_id = os.getenv(ENV_TENANT_ID, None)
    if not tenant_id:
        raise Exception(f"{ENV_TENANT_ID} env var is not set")
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/apps_/default/api/v1/default/deployed-action-apps-schemas"),
        params={"search": app_name},
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


class ActionsService(FolderContext, BaseService):
    """Service for managing UiPath Actions.

    Actions are task-based automation components that can be integrated into
    applications and processes. They represent discrete units of work that can
    be triggered and monitored through the UiPath API.

    This service provides methods to create and retrieve actions, supporting
    both app-specific and generic actions. It inherits folder context management
    capabilities from FolderContext.

    Reference: https://docs.uipath.com/automation-cloud/docs/actions
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="actions_create", run_type="uipath")
    async def create_async(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_name: Optional[str] = None,
        app_key: Optional[str] = None,
        app_folder_path: Optional[str] = None,
        app_folder_key: Optional[str] = None,
        app_version: Optional[int] = 1,
        assignee: Optional[str] = None,
    ) -> Action:
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
            app_version: The version of the application
            assignee: Optional username or email to assign the task to

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
            app_version=app_version,
            action_schema=action_schema,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
        )

        response = await self.request_async(
            spec.method, spec.endpoint, content=spec.content, headers=spec.headers
        )
        json_response = response.json()
        if assignee:
            spec = _assign_task_spec(json_response["id"], assignee)
            await self.request_async(spec.method, spec.endpoint, content=spec.content)
        return Action.model_validate(json_response)

    @traced(name="actions_create", run_type="uipath")
    def create(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_name: Optional[str] = None,
        app_key: Optional[str] = None,
        app_folder_path: Optional[str] = None,
        app_folder_key: Optional[str] = None,
        app_version: Optional[int] = 1,
        assignee: Optional[str] = None,
    ) -> Action:
        """Creates a new action synchronously.

        This method creates a new action task in UiPath Orchestrator. The action can be
        either app-specific (using app_name or app_key) or a generic action.

        Args:
            title: The title of the action
            data: Optional dictionary containing input data for the action
            app_name: The name of the application (if creating an app-specific action)
            app_key: The key of the application (if creating an app-specific action)
            app_folder_path: Optional folder path for the action
            app_folder_key: Optional folder key for the action
            app_version: The version of the application
            assignee: Optional username or email to assign the task to

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
            app_version=app_version,
            action_schema=action_schema,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
        )

        response = self.request(
            spec.method, spec.endpoint, content=spec.content, headers=spec.headers
        )
        json_response = response.json()
        if assignee:
            spec = _assign_task_spec(json_response["id"], assignee)
            self.request(spec.method, spec.endpoint, content=spec.content)
        return Action.model_validate(json_response)

    @traced(name="actions_retrieve", run_type="uipath")
    def retrieve(
        self, action_key: str, app_folder_path: str = "", app_folder_key: str = ""
    ) -> Action:
        """Retrieves an action by its key synchronously.

        Args:
            action_key: The unique identifier of the action to retrieve
            app_folder_path: Optional folder path for the action
            app_folder_key: Optional folder key for the action

        Returns:
            Action: The retrieved action object
        """
        spec = _retrieve_action_spec(
            action_key=action_key,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
        )
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )

        return Action.model_validate(response.json())

    @traced(name="actions_retrieve", run_type="uipath")
    async def retrieve_async(
        self, action_key: str, app_folder_path: str = "", app_folder_key: str = ""
    ) -> Action:
        """Retrieves an action by its key asynchronously.

        Args:
            action_key: The unique identifier of the action to retrieve
            app_folder_path: Optional folder path for the action
            app_folder_key: Optional folder key for the action

        Returns:
            Action: The retrieved action object
        """
        spec = _retrieve_action_spec(
            action_key=action_key,
            app_folder_key=app_folder_key,
            app_folder_path=app_folder_path,
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )

        return Action.model_validate(response.json())

    async def _get_app_key_and_schema_async(
        self, app_name: Optional[str], app_folder_path: Optional[str]
    ) -> Tuple[str, Optional[ActionSchema]]:
        if not app_name:
            raise Exception("appName or appKey is required")
        spec = _retrieve_app_key_spec(app_name=app_name)

        response = await self.request_org_scope_async(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
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
                ActionSchema(
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
    ) -> Tuple[str, Optional[ActionSchema]]:
        if not app_name:
            raise Exception("appName or appKey is required")

        spec = _retrieve_app_key_spec(app_name=app_name)

        response = self.request_org_scope(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
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
                ActionSchema(
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
