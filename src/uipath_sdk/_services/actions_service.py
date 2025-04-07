import os
import uuid
from json import dumps
from typing import Any, Dict, Optional, Tuple

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Action, ActionSchema
from .._utils import Endpoint, RequestSpec
from .._utils.constants import ENV_TENANT_ID, HEADER_TENANT_ID
from ._base_service import BaseService


def _create_spec(
    title: str,
    data: Optional[Dict[str, Any]],
    action_schema: Optional[ActionSchema],
    app_key: str = "",
    app_version: int = -1,
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
    )


def _retrieve_action_spec(action_key: str) -> RequestSpec:
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/orchestrator_/tasks/GenericTasks/GetTaskDataByKey"),
        params={"taskKey": action_key},
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


class ActionsService(FolderContext, BaseService):
    """Service for managing UiPath Actions.

    Actions are task-based automation components that can be integrated into
    applications and processes. They represent discrete units of work that can
    be triggered and monitored through the UiPath API.

    This service provides methods to create and retrieve actions, supporting
    both app-specific and generic actions. It inherits folder context management
    capabilities from FolderContext.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    async def create_async(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_name: str = "",
        app_key: str = "",
        app_version: int = -1,
        assignee: str = "",
    ) -> Action:
        (key, action_schema) = (
            (app_key, None)
            if app_key
            else await self.__get_app_key_and_schema_async(app_name)
        )
        spec = _create_spec(
            title=title,
            data=data,
            app_key=key,
            app_version=app_version,
            action_schema=action_schema,
        )

        response = await self.request_async(
            spec.method, spec.endpoint, content=spec.content
        )
        json_response = response.json()
        if assignee:
            spec = _assign_task_spec(json_response["id"], assignee)
            await self.request_async(spec.method, spec.endpoint, content=spec.content)
        return Action.model_validate(json_response)

    def create(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_name: str = "",
        app_key: str = "",
        app_version: int = -1,
        assignee: str = "",
    ) -> Action:
        (key, action_schema) = (
            (app_key, None) if app_key else self.__get_app_key_and_schema(app_name)
        )
        spec = _create_spec(
            title=title,
            data=data,
            app_key=key,
            app_version=app_version,
            action_schema=action_schema,
        )

        response = self.request(spec.method, spec.endpoint, content=spec.content)
        json_response = response.json()
        if assignee:
            spec = _assign_task_spec(json_response["id"], assignee)
            print(spec)
            self.request(spec.method, spec.endpoint, content=spec.content)
        return Action.model_validate(json_response)

    def retrieve(
        self,
        action_key: str,
    ) -> Action:
        spec = _retrieve_action_spec(action_key=action_key)
        response = self.request(spec.method, spec.endpoint, params=spec.params)

        return Action.model_validate(response.json())

    async def retrieve_async(
        self,
        action_key: str,
    ) -> Action:
        spec = _retrieve_action_spec(action_key=action_key)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params
        )

        return Action.model_validate(response.json())

    async def __get_app_key_and_schema_async(
        self, app_name: str
    ) -> Tuple[str, Optional[ActionSchema]]:
        if not app_name:
            raise Exception("appName or appKey is required")
        spec = _retrieve_app_key_spec(app_name=app_name)

        response = await self.request_org_scope_async(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )
        deployed_app = response.json()["deployed"][0]
        return (deployed_app["systemName"], deployed_app["actionSchema"])

    def __get_app_key_and_schema(
        self, app_name: str
    ) -> Tuple[str, Optional[ActionSchema]]:
        if not app_name:
            raise Exception("appName or appKey is required")

        spec = _retrieve_app_key_spec(app_name=app_name)

        response = self.request_org_scope(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )

        deployed_app = response.json()["deployed"][0]
        action_schema = deployed_app["actionSchema"]
        return (
            deployed_app["systemName"],
            ActionSchema(
                key=action_schema["key"],
                in_outs=action_schema["inOuts"],
                inputs=action_schema["inputs"],
                outputs=action_schema["outputs"],
                outcomes=action_schema["outcomes"],
            ),
        )

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
