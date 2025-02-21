from typing import Dict

from httpx import request

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from ._base_service import BaseService


class BucketsService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def download(
        self,
        bucket_id: str,
        blob_file_path: str,
        destination_path: str,
    ) -> None:
        endpoint = f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetReadUri?path={blob_file_path}"

        result = self.request("GET", endpoint).json()
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
        bucket_id: str,
        blob_file_path: str,
        content_type: str,
        source_path: str,
    ) -> None:
        endpoint = f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetWriteUri?path={blob_file_path}&contentType={content_type}"

        result = self.request("GET", endpoint).json()
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

    def get_bucket_id(self, bucket_name: str) -> str:
        endpoint = f"/orchestrator_/odata/Buckets?$top=1&$filter=(contains(Name,%27{bucket_name}%27))&$orderby=Name%20asc"

        response = self.request("GET", endpoint)
        key = response.json()["value"][0]["Id"]
        return key

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers
