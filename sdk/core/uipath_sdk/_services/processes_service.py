from typing import Dict

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Process
from .._utils import Endpoint
from ._base_service import BaseService


class ProcessesService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def invoke(self, name: str) -> Response:
        endpoint = Endpoint(
            "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )

        process = self.retrieve_by_name(name)
        process_key = process.Key

        content = str({"startInfo": {"ReleaseKey": process_key}})

        return self.request(
            "POST",
            endpoint,
            content=content,
        )

    def retrieve_by_name(self, name: str) -> Process:
        endpoint = Endpoint(
            "/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases"
        )
        params = {"$filter": f"Name eq '{name}'", "$top": 1}

        try:
            response = self.request(
                "GET",
                url=endpoint,
                params=params,
            )
        except Exception as e:
            raise Exception(f"Process with name {name} not found") from e

        return Process.model_validate(response.json()["value"][0])

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
