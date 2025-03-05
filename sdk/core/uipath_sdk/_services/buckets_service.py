from typing import Dict

from httpx import Response, request

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class BucketsService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def retrieve(self, key: str) -> Response:
        spec = self._retrieve_spec(key)
        return self.request(spec.method, url=spec.endpoint)

    async def retrieve_async(self, key: str) -> Response:
        spec = self._retrieve_spec(key)
        return await self.request_async(spec.method, url=spec.endpoint)

    def download(
        self,
        bucket_key: str,
        blob_file_path: str,
        destination_path: str,
    ) -> None:
        bucket = self.retrieve(bucket_key).json()
        bucket_id = bucket["Id"]
        endpoint = Endpoint(
            f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetReadUri"
        )

        result = self.request("GET", endpoint, params={"path": blob_file_path}).json()
        read_uri = result["Uri"]

        headers = {
            key: value
            for key, value in zip(
                result["Headers"]["Keys"], result["Headers"]["Values"]
            )
        }

        with open(destination_path, "wb") as file:
            # the self.request adds auth bearer token
            if result["RequiresAuth"]:
                file_content = self.request("GET", read_uri, headers=headers).content
            else:
                file_content = request("GET", read_uri, headers=headers).content
            file.write(file_content)

    def upload(
        self,
        bucket_key: str,
        blob_file_path: str,
        content_type: str,
        source_path: str,
    ) -> None:
        bucket = self.retrieve(bucket_key).json()
        bucket_id = bucket["Id"]
        endpoint = Endpoint(
            f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetWriteUri"
        )

        result = self.request(
            "GET",
            endpoint,
            params={"path": blob_file_path, "contentType": content_type},
        ).json()
        write_uri = result["Uri"]

        headers = {
            key: value
            for key, value in zip(
                result["Headers"]["Keys"], result["Headers"]["Values"]
            )
        }

        with open(source_path, "rb") as file:
            if result["RequiresAuth"]:
                self.request("PUT", write_uri, headers=headers, files={"file": file})
            else:
                request("PUT", write_uri, headers=headers, files={"file": file})

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _retrieve_spec(self, key: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={key})"
            ),
        )
