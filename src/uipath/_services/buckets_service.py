from typing import Any, Dict, Optional, Union

from httpx import request

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, infer_bindings
from ..models import Bucket
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
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        blob_file_path: str,
        destination_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Download a file from a bucket.

        Args:
            key (Optional[str]): The key of the bucket.
            name (Optional[str]): The name of the bucket.
            blob_file_path (str): The path to the file in the bucket.
            destination_path (str): The local path where the file will be saved.
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Raises:
            ValueError: If neither key nor name is provided.
            Exception: If the bucket with the specified key is not found.
        """
        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )
        spec = self._retrieve_readUri_spec(
            bucket, blob_file_path, folder_key=folder_key, folder_path=folder_path
        )
        result = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()

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
        key: Optional[str] = None,
        name: Optional[str] = None,
        blob_file_path: str,
        content_type: str,
        source_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Upload a file to a bucket.

        Args:
            key (Optional[str]): The key of the bucket.
            name (Optional[str]): The name of the bucket.
            blob_file_path (str): The path where the file will be stored in the bucket.
            content_type (str): The MIME type of the file.
            source_path (str): The local path of the file to upload.
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Raises:
            ValueError: If neither key nor name is provided.
            Exception: If the bucket with the specified key or name is not found.
        """
        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        bucket_id = bucket["Id"]

        spec = self._retrieve_writeri_spec(
            bucket_id,
            content_type,
            blob_file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        result = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
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

    @traced(name="buckets_upload", run_type="uipath")
    async def upload_async(
        self,
        *,
        key: Optional[str] = None,
        name: Optional[str] = None,
        blob_file_path: str,
        content_type: str,
        source_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Upload a file to a bucket asynchronously.

        Args:
            key (Optional[str]): The key of the bucket.
            name (Optional[str]): The name of the bucket.
            blob_file_path (str): The path where the file will be stored in the bucket.
            content_type (str): The MIME type of the file.
            source_path (str): The local path of the file to upload.
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Raises:
            ValueError: If neither key nor name is provided.
            Exception: If the bucket with the specified key or name is not found.
        """
        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        bucket_id = bucket["Id"]

        spec = self._retrieve_writeri_spec(
            bucket_id,
            content_type,
            blob_file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        result = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
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
                await self.request_async(
                    "PUT", write_uri, headers=headers, files={"file": file}
                )
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
        key: Optional[str] = None,
        name: Optional[str] = None,
        blob_file_path: str,
        content_type: str,
        content: Union[str, bytes],
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Upload content from memory to a bucket.

        Args:
            key (Optional[str]): The key of the bucket.
            name (Optional[str]): The name of the bucket.
            blob_file_path (str): The path where the content will be stored in the bucket.
            content_type (str): The MIME type of the content.
            content (Union[str, bytes]): The content to upload (string or bytes).
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Raises:
            ValueError: If neither key nor name is provided.
            Exception: If the bucket with the specified key or name is not found.
        """
        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )
        bucket_id = bucket["Id"]

        spec = self._retrieve_writeri_spec(
            bucket_id,
            content_type,
            blob_file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        result = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
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

    async def upload_from_memory_async(
        self,
        *,
        key: Optional[str] = None,
        name: Optional[str] = None,
        blob_file_path: str,
        content_type: str,
        content: Union[str, bytes],
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Asynchronously upload content from memory to a bucket.

        Args:
            key (Optional[str]): The key of the bucket.
            name (Optional[str]): The name of the bucket.
            blob_file_path (str): The path where the content will be stored in the bucket.
            content_type (str): The MIME type of the content.
            content (Union[str, bytes]): The content to upload (string or bytes).
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Raises:
            ValueError: If neither key nor name is provided.
            Exception: If the bucket with the specified key or name is not found.
        """
        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        bucket_id = bucket["Id"]

        spec = self._retrieve_writeri_spec(
            bucket_id,
            content_type,
            blob_file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        result = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
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
            await self.request_async("PUT", write_uri, headers=headers, content=content)
        else:
            request("PUT", write_uri, headers=headers, content=content)

    @infer_bindings()
    @traced(name="buckets_retrieve", run_type="uipath")
    def retrieve(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Bucket:
        """Retrieve bucket information by its name.

        Args:
            name (Optional[str]): The name of the bucket to retrieve.
            key (Optional[str]): The key of the bucket.
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Returns:
            Response: The bucket details.

        Raises:
            ValueError: If neither bucket key nor bucket name is provided.
            Exception: If the bucket with the specified name is not found.
        """
        if not (key or name):
            raise ValueError("Must specify a bucket name or bucket key")
        if key:
            spec = self._retrieve_by_key_spec(
                key, folder_key=folder_key, folder_path=folder_path
            )
        else:
            spec = self._retrieve_spec(
                name,  # type: ignore
                folder_key=folder_key,
                folder_path=folder_path,
            )
        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()["value"][0]
        except (KeyError, IndexError) as e:
            raise Exception(f"Bucket with name '{name}' not found") from e
        return Bucket.model_validate(response)

    @infer_bindings()
    @traced(name="buckets_retrieve", run_type="uipath")
    async def retrieve_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Bucket:
        """Asynchronously retrieve bucket information by its name.

        Args:
            name (Optional[str]): The name of the bucket to retrieve.
            key (Optional[str]): The key of the bucket.
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Returns:
            Response: The bucket details.

        Raises:
            ValueError: If neither bucket key nor bucket name is provided.
            Exception: If the bucket with the specified name is not found.
        """
        if not (key or name):
            raise ValueError("Must specify a bucket name or bucket key")
        if key:
            spec = self._retrieve_by_key_spec(
                key, folder_key=folder_key, folder_path=folder_path
            )
        else:
            spec = self._retrieve_spec(
                name,  # type: ignore
                folder_key=folder_key,
                folder_path=folder_path,
            )

        try:
            response = (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                )
            ).json()["value"][0]
        except (KeyError, IndexError) as e:
            raise Exception(f"Bucket with name '{name}' not found") from e
        return Bucket.model_validate(response)

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _retrieve_spec(
        self,
        name: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Buckets"),
            params={"$filter": f"Name eq '{name}'", "$top": 1},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_readUri_spec(
        self,
        bucket_id: str,
        blob_file_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetReadUri"
            ),
            params={"path": blob_file_path},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_writeri_spec(
        self,
        bucket_id: str,
        content_type: str,
        blob_file_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetWriteUri"
            ),
            params={"path": blob_file_path, "contentType": content_type},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_by_key_spec(
        self,
        key: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={key})"
            ),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
