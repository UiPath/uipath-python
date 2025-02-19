from typing import Any, Dict, Optional, cast

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Action
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
        :param app_id: The `systemName` of the app.
        :param app_version: The `deployVersion` of the app.
        :param title: The title of the task.
        """

        endpoint = "/orchestrator_/tasks/AppTasks/CreateAppTask"
        content = str(
            {
                "appId": app_id,
                "appVersion": app_version,
                "title": title,
                "data": data if data is not None else {},
            }
        )

        return cast(
            Action,
            self.request(
                "POST",
                endpoint,
                content=content,
            ).json(),
        )

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
