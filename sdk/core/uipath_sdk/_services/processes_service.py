from typing import Dict

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import Process
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class ProcessesService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def invoke(self, name: str) -> Response:
        process = self.retrieve_by_name(name)
        process_key = process.Key

        spec = self._invoke_spec(process_key)

        return self.request(spec.method, url=spec.endpoint, content=spec.content)

    async def invoke_async(self, name: str) -> Response:
        process = await self.retrieve_by_name_async(name)
        process_key = process.Key

        spec = self._invoke_spec(process_key)

        return await self.request_async(
            spec.method, url=spec.endpoint, content=spec.content
        )

    def retrieve_by_name(self, name: str) -> Process:
        spec = self._retrieve_by_name_spec(name)

        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            )
        except Exception as e:
            raise Exception(f"Process with name {name} not found") from e

        return Process.model_validate(response.json()["value"][0])

    async def retrieve_by_name_async(self, name: str) -> Process:
        spec = self._retrieve_by_name_spec(name)

        try:
            response = await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            )
        except Exception as e:
            raise Exception(f"Process with name {name} not found") from e

        return Process.model_validate(response.json()["value"][0])

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _invoke_spec(self, process_key: str) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
            ),
            content=str({"startInfo": {"ReleaseKey": process_key}}),
        )

    def _retrieve_by_name_spec(self, name: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                "/orchestrator_/odata/Releases/UiPath.Server.Configuration.OData.ListReleases"
            ),
            params={"$filter": f"Name eq '{name}'", "$top": 1},
        )
