from typing import Any, Dict, Optional, Union

from httpx import request

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, infer_bindings
from ..tracing._traced import traced
from ._base_service import BaseService


def _upload_from_memory_input_processor(inputs: Dict[str, Any]) -> Dict[str, Any]:
    inputs["content"] = "<Redacted>"
    return inputs


class BucketsService(FolderContext, BaseService):
    """Service for managing UiPath storage buckets.

    Buckets are cloud storage containers that can be used to store and manage files
    used by automation processes.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="buckets_download", run_type="uipath")
    def download(
        self,
        bucket_key: str,
        blob_file_path: str,
        destination_path: str,
    ) -> None:
        """Download a file from a bucket.

        Args:
            bucket_key: The key of the bucket
            blob_file_path: The path to the file in the bucket
            destination_path: The local path where the file will be saved
        """
        bucket = self.retrieve_by_key(bucket_key)
        bucket_id = bucket["Id"]

        endpoint = Endpoint(
            f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetReadUri"
        )

        result = self.request("GET", endpoint, params={"path": blob_file_path}).json()
        read_uri = result["Uri"]

        headers = {
            key: value
            for key, value in zip(
                result["Headers"]["Keys"], result["Headers"]["Values"], strict=False
            )
        }

        with open(destination_path, "wb") as file:
            # the self.request adds auth bearer token
            if result["RequiresAuth"]:
                file_content = self.request("GET", read_uri, headers=headers).content
            else:
                file_content = request("GET", read_uri, headers=headers).content
            file.write(file_content)

    @traced(name="buckets_upload", run_type="uipath")
    def upload(
        self,
        *,
        bucket_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        blob_file_path: str,
        content_type: str,
        source_path: str,
    ) -> None:
        """Upload a file to a bucket.

        Args:
            bucket_key: The key of the bucket
            bucket_name: The name of the bucket
            blob_file_path: The path where the file will be stored in the bucket
            content_type: The MIME type of the file
            source_path: The local path of the file to upload
        """
        if bucket_key:
            bucket = self.retrieve_by_key(bucket_key)
        elif bucket_name:
            bucket = self.retrieve(bucket_name)
        else:
            raise ValueError("Must specify a bucket name or bucket key")

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
                result["Headers"]["Keys"], result["Headers"]["Values"], strict=False
            )
        }

        with open(source_path, "rb") as file:
            if result["RequiresAuth"]:
                self.request("PUT", write_uri, headers=headers, files={"file": file})
            else:
                request("PUT", write_uri, headers=headers, files={"file": file})

    @traced(
        name="buckets_upload_from_memory",
        run_type="uipath",
        input_processor=_upload_from_memory_input_processor,
    )
    def upload_from_memory(
        self,
        *,
        bucket_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        blob_file_path: str,
        content_type: str,
        content: Union[str, bytes],
    ) -> None:
        """Upload content from memory to a bucket.

        Args:
            bucket_key: The key of the bucket
            bucket_name: The name of the bucket
            blob_file_path: The path where the content will be stored in the bucket
            content_type: The MIME type of the content
            content: The content to upload (string or bytes)
        """
        if bucket_key:
            bucket = self.retrieve_by_key(bucket_key)
        elif bucket_name:
            bucket = self.retrieve(bucket_name)
        else:
            raise ValueError("Must specify a bucket name or bucket key")

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
                result["Headers"]["Keys"], result["Headers"]["Values"], strict=False
            )
        }

        # Convert string to bytes if needed
        if isinstance(content, str):
            content = content.encode("utf-8")

        if result["RequiresAuth"]:
            self.request("PUT", write_uri, headers=headers, content=content)
        else:
            request("PUT", write_uri, headers=headers, content=content)

    @infer_bindings()
    @traced(name="buckets_retrieve", run_type="uipath")
    def retrieve(self, name: str) -> Any:
        """Retrieve bucket information by its name.

        Args:
            name (str): The name of the bucket to retrieve.

        Returns:
            Response: The HTTP response containing the bucket details, including
                its ID, name, and configuration.
        """
        spec = self._retrieve_spec(name)

        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            )
        except Exception as e:
            raise Exception(f"Bucket with name {name} not found") from e

        return response.json()["value"][0]

    @infer_bindings()
    @traced(name="buckets_retrieve", run_type="uipath")
    async def retrieve_async(self, name: str) -> Any:
        """Asynchronously retrieve bucket information by its name.

        Args:
            name (str): The name of the bucket to retrieve.

        Returns:
            Response: The HTTP response containing the bucket details, including
                its ID, name, and configuration.
        """
        spec = self._retrieve_spec(name)

        try:
            response = await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
            )
        except Exception as e:
            raise Exception(f"Bucket with name {name} not found") from e

        return response.json()["value"][0]

    @traced(name="buckets_retrieve_by_key", run_type="uipath")
    def retrieve_by_key(self, key: str) -> Any:
        """Retrieve bucket information by its key.

        Args:
            key (str): The key of the bucket

        Returns:
            Response: The HTTP response containing the bucket details, including
                its ID, name, and configuration.
        """
        spec = self._retrieve_by_key_spec(key)

        try:
            response = self.request(spec.method, url=spec.endpoint)
        except Exception as e:
            raise Exception(f"Bucket with key {key} not found") from e

        return response.json()

    @traced(name="buckets_retrieve_by_key", run_type="uipath")
    async def retrieve_by_key_async(self, key: str) -> Any:
        """Asynchronously retrieve bucket information by its key.

        Args:
            key (str): The key of the bucket

        Returns:
            Response: The HTTP response containing the bucket details, including
                its ID, name, and configuration.
        """
        spec = self._retrieve_by_key_spec(key)

        try:
            response = await self.request_async(spec.method, url=spec.endpoint)
        except Exception as e:
            raise Exception(f"Bucket with key {key} not found") from e

        return response.json()

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _retrieve_spec(self, name: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Buckets"),
            params={"$filter": f"Name eq '{name}'", "$top": 1},
        )

    def _retrieve_by_key_spec(self, key: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={key})"
            ),
        )
