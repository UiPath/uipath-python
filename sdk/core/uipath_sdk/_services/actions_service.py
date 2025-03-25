import os
from json import dumps
from typing import Any, Dict, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Action
from .._utils import Endpoint, RequestSpec
from .._utils.constants import ENV_TENANT_ID, HEADER_TENANT_ID
from ._base_service import BaseService


def _create_spec(
    title: str, data: Optional[Dict[str, Any]], app_key: str = "", app_version: int = -1
) -> RequestSpec:
    return RequestSpec(
        method="POST",
        endpoint=Endpoint("/orchestrator_/tasks/AppTasks/CreateAppTask"),
        content=dumps(
            {
                "appId": app_key,
                "appVersion": app_version,
                "title": title,
                "data": data if data is not None else {},
            }
        ),
    )


def _retrieve_action_spec(action_key: str) -> RequestSpec:
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/orchestrator_/tasks/GenericTasks/GetTaskDataByKey"),
        params={"taskKey": action_key},
    )


def _retrieve_app_key_spec(app_name: str) -> RequestSpec:
    tenant_id = os.getenv(ENV_TENANT_ID, None)
    if not tenant_id:
        raise Exception(f"{ENV_TENANT_ID} env var is not set")
    return RequestSpec(
        method="GET",
        endpoint=Endpoint("/apps_/default/api/v1/default/action-apps"),
        params={"search": app_name, "state": "deployed"},
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
    ) -> Action:
        key = app_key if app_key else await self.__get_app_key_async(app_name)
        spec = _create_spec(
            title=title, data=data, app_key=key, app_version=app_version
        )

        response = await self.request_async(
            spec.method, spec.endpoint, content=spec.content
        )

        return Action.model_validate(response.json())

    def create(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_name: str = "",
        app_key: str = "",
        app_version: int = -1,
    ) -> Action:
        key = app_key if app_key else self.__get_app_key(app_name)
        spec = _create_spec(
            title=title, data=data, app_key=key, app_version=app_version
        )

        response = self.request(spec.method, spec.endpoint, content=spec.content)

        return Action.model_validate(response.json())

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

    async def __get_app_key_async(self, app_name: str) -> str:
        if not app_name:
            raise Exception("appName or appKey is required")
        spec = _retrieve_app_key_spec(app_name=app_name)

        response = await self.request_org_scope_async(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )

        return response.json()["deployed"][0]["systemName"]

    def __get_app_key(self, app_name: str) -> str:
        if not app_name:
            raise Exception("appName or appKey is required")

        spec = _retrieve_app_key_spec(app_name=app_name)

        response = self.request_org_scope(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )

        return response.json()["deployed"][0]["systemName"]

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
