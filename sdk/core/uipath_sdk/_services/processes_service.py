from typing import Dict

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from ._base_service import BaseService


class ProcessesService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

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
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
