from typing import Dict

from httpx import Response, request

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class BucketsService(FolderContext, BaseService):
    """
    Service for managing UiPath storage buckets.

    Buckets are cloud storage containers that can be used to store and manage files
    used by automation processes. This service provides methods to retrieve bucket
    information and perform file operations (upload/download) within buckets.

    The service supports both synchronous and asynchronous operations for bucket
    retrieval, and provides direct file transfer capabilities with automatic
    authentication handling.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        """
        Initialize the buckets service.

        Args:
            config (Config): Configuration object containing API settings.
            execution_context (ExecutionContext): Context object containing execution-specific
                information.
        """
        super().__init__(config=config, execution_context=execution_context)

    def retrieve(self, key: str) -> Response:
        """
        Retrieve bucket information by its key.

        Args:
            key (str): The unique identifier of the bucket to retrieve.

        Returns:
            Response: The HTTP response containing the bucket details, including
                its ID, name, and configuration.
        """
        spec = self._retrieve_spec(key)
        return self.request(spec.method, url=spec.endpoint)

    async def retrieve_async(self, key: str) -> Response:
        """
        Asynchronously retrieve bucket information by its key.

        Args:
            key (str): The unique identifier of the bucket to retrieve.

        Returns:
            Response: The HTTP response containing the bucket details, including
                its ID, name, and configuration.
        """
        spec = self._retrieve_spec(key)
        return await self.request_async(spec.method, url=spec.endpoint)

    def download(
        self,
        bucket_key: str,
        blob_file_path: str,
        destination_path: str,
    ) -> None:
        """
        Download a file from a bucket to a local destination.

        This method handles the entire download process, including:
        1. Retrieving bucket information
        2. Getting a secure download URL
        3. Handling authentication if required
        4. Saving the file to the specified destination

        Args:
            bucket_key (str): The unique identifier of the bucket containing the file.
            blob_file_path (str): The path to the file within the bucket.
            destination_path (str): The local path where the file should be saved.

        Example:
            ```python
            # Download a configuration file from a bucket
            buckets_service.download(
                bucket_key="my-bucket",
                blob_file_path="configs/app-config.json",
                destination_path="/local/path/app-config.json"
            )
            ```
        """
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
        """
        Upload a local file to a bucket.

        This method handles the entire upload process, including:
        1. Retrieving bucket information
        2. Getting a secure upload URL
        3. Handling authentication if required
        4. Uploading the file with the specified content type

        Args:
            bucket_key (str): The unique identifier of the bucket to upload to.
            blob_file_path (str): The desired path for the file within the bucket.
            content_type (str): The MIME type of the file being uploaded.
            source_path (str): The local path of the file to upload.

        Example:
            ```python
            # Upload a configuration file to a bucket
            buckets_service.upload(
                bucket_key="my-bucket",
                blob_file_path="configs/app-config.json",
                content_type="application/json",
                source_path="/local/path/app-config.json"
            )
            ```
        """
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
        """
        Get custom headers for bucket-related requests.

        Returns:
            Dict[str, str]: Headers containing folder context information.
        """
        return self.folder_headers

    def _retrieve_spec(self, key: str) -> RequestSpec:
        """
        Create a request specification for retrieving bucket information.

        Args:
            key (str): The unique identifier of the bucket.

        Returns:
            RequestSpec: The request specification for the API call.
        """
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={key})"
            ),
        )
