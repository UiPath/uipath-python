from json import dumps
from typing import Any, Dict, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Action
from .._utils import Endpoint
from ._base_service import BaseService


class ActionsService(FolderContext, BaseService):
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
        """
        Create a new action.

        Args:
            title: The title of the action.
            data: Optional dictionary of additional data.
            app_id: The `systemName` of the app.
            app_version: The `deployVersion` of the app.

        Returns:
            Action: The created action.
        """
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
        """
        Retrieve an action by key.

        Args:
            action_key: The key of the action to retrieve.

        Returns:
            Action: The retrieved action.
        """
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
