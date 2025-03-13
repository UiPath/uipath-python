from json import dumps
from typing import Any, Dict, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Action
from .._utils import Endpoint
from ._base_service import BaseService


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

    def create(
        self,
        title: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        app_id: str = "",
        app_version: int = -1,
    ) -> Action:
        endpoint = Endpoint("/orchestrator_/tasks/AppTasks/CreateAppTask")

        content = dumps(
            {
                "appId": app_id,
                "appVersion": app_version,
                "title": title,
                "data": data if data is not None else {},
            }
        )

        response = self.request(
            "POST",
            endpoint,
            content=content,
        )

        return Action.model_validate(response.json())

    def retrieve(
        self,
        action_key: str,
    ) -> Action:
        endpoint = Endpoint("/orchestrator_/tasks/GenericTasks/GetTaskDataByKey")
        params = {"taskKey": action_key}

        response = self.request(
            "GET",
            endpoint,
            params=params,
        )

        return Action.model_validate(response.json())

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
