from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from ._base_service import BaseService


class TasksService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def create_task(self, app_id: str, app_version: int, title: str) -> Response:
        """
        :param app_id: The `systemName` of the app.
        :param app_version: The `deployVersion` of the app.
        :param title: The title of the task.
        """
        endpoint = "/orchestrator_/tasks/AppTasks/CreateAppTask"
        content = str(
            {"appId": app_id, "appVersion": app_version, "title": title, "data": {}}
        )

        return self.request(
            "POST",
            endpoint,
            content=content,
        )

    @property
    def custom_headers(self) -> dict[str, str]:
        return self.folder_headers
