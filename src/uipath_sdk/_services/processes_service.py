from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from ._base_service import BaseService


class ProcessesService(BaseService, FolderContext):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        BaseService.__init__(self, config, execution_context)
        FolderContext.__init__(self)

    def invoke(self, release_key: str) -> Response:
        endpoint = (
            "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )
        content = str({"startInfo": {"ReleaseKey": release_key}})

        return self.request(
            "POST",
            endpoint,
            content=content,
        )

    @property
    def custom_headers(self) -> dict[str, str]:
        return self.folder_headers
