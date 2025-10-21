import mimetypes
from typing import Dict, Optional, Union

import httpx

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, infer_bindings
from .._utils._ssl_context import get_httpx_client_kwargs
from ..models import Bucket
from ..tracing._traced import traced
from ._base_service import BaseService


class BucketsService(FolderContext, BaseService):
    """Service for managing UiPath storage buckets.

    Buckets are cloud storage containers that can be used to store and manage files
    used by automation processes.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self.custom_client = httpx.Client(**get_httpx_client_kwargs())
        self.custom_client_async = httpx.AsyncClient(**get_httpx_client_kwargs())

    @traced(name="buckets_download", run_type="uipath")
    @infer_bindings(resource_type="bucket")
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
            bucket.id, blob_file_path, folder_key=folder_key, folder_path=folder_path
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
                file_content = self.custom_client.get(read_uri, headers=headers).content
            file.write(file_content)

    @traced(name="buckets_download", run_type="uipath")
    @infer_bindings(resource_type="bucket")
    async def download_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        blob_file_path: str,
        destination_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Download a file from a bucket asynchronously.

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
        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )
        spec = self._retrieve_readUri_spec(
            bucket.id, blob_file_path, folder_key=folder_key, folder_path=folder_path
        )
        result = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
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
                file_content = (
                    await self.request_async("GET", read_uri, headers=headers)
                ).content
            else:
                file_content = (
                    await self.custom_client_async.get(read_uri, headers=headers)
                ).content
            file.write(file_content)

    @traced(name="buckets_upload", run_type="uipath")
    @infer_bindings(resource_type="bucket")
    def upload(
        self,
        *,
        key: Optional[str] = None,
        name: Optional[str] = None,
        blob_file_path: str,
        content_type: Optional[str] = None,
        source_path: Optional[str] = None,
        content: Optional[Union[str, bytes]] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Upload a file to a bucket.

        Args:
            key (Optional[str]): The key of the bucket.
            name (Optional[str]): The name of the bucket.
            blob_file_path (str): The path where the file will be stored in the bucket.
            content_type (Optional[str]): The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream".
            source_path (Optional[str]): The local path of the file to upload.
            content (Optional[Union[str, bytes]]): The content to upload (string or bytes).
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Raises:
            ValueError: If neither key nor name is provided.
            Exception: If the bucket with the specified key or name is not found.
        """
        if content is not None and source_path is not None:
            raise ValueError("Content and source_path are mutually exclusive")
        if content is None and source_path is None:
            raise ValueError("Either content or source_path must be provided")

        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        # if source_path, dynamically detect the mime type
        # default to application/octet-stream
        if source_path:
            _content_type, _ = mimetypes.guess_type(source_path)
        else:
            _content_type = content_type
        _content_type = _content_type or "application/octet-stream"

        spec = self._retrieve_writeri_spec(
            bucket.id,
            _content_type,
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

        headers["Content-Type"] = _content_type

        if content is not None:
            if isinstance(content, str):
                content = content.encode("utf-8")

            if result["RequiresAuth"]:
                self.request("PUT", write_uri, headers=headers, content=content)
            else:
                self.custom_client.put(write_uri, headers=headers, content=content)

        if source_path is not None:
            with open(source_path, "rb") as file:
                file_content = file.read()
                if result["RequiresAuth"]:
                    self.request(
                        "PUT", write_uri, headers=headers, content=file_content
                    )
                else:
                    self.custom_client.put(
                        write_uri, headers=headers, content=file_content
                    )

    @traced(name="buckets_upload", run_type="uipath")
    @infer_bindings(resource_type="bucket")
    async def upload_async(
        self,
        *,
        key: Optional[str] = None,
        name: Optional[str] = None,
        blob_file_path: str,
        content_type: Optional[str] = None,
        source_path: Optional[str] = None,
        content: Optional[Union[str, bytes]] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Upload a file to a bucket asynchronously.

        Args:
            key (Optional[str]): The key of the bucket.
            name (Optional[str]): The name of the bucket.
            blob_file_path (str): The path where the file will be stored in the bucket.
            content_type (Optional[str]): The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream".
            source_path (str): The local path of the file to upload.
            content (Optional[Union[str, bytes]]): The content to upload (string or bytes).
            folder_key (Optional[str]): The key of the folder where the bucket resides.
            folder_path (Optional[str]): The path of the folder where the bucket resides.

        Raises:
            ValueError: If neither key nor name is provided.
            Exception: If the bucket with the specified key or name is not found.
        """
        if content is not None and source_path is not None:
            raise ValueError("Content and source_path are mutually exclusive")
        if content is None and source_path is None:
            raise ValueError("Either content or source_path must be provided")

        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        # if source_path, dynamically detect the mime type
        # default to application/octet-stream
        if source_path:
            _content_type, _ = mimetypes.guess_type(source_path)
        else:
            _content_type = content_type
        _content_type = _content_type or "application/octet-stream"

        spec = self._retrieve_writeri_spec(
            bucket.id,
            _content_type,
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

        headers["Content-Type"] = _content_type

        if content is not None:
            if isinstance(content, str):
                content = content.encode("utf-8")

            if result["RequiresAuth"]:
                await self.request_async(
                    "PUT", write_uri, headers=headers, content=content
                )
            else:
                await self.custom_client_async.put(
                    write_uri, headers=headers, content=content
                )

        if source_path is not None:
            with open(source_path, "rb") as file:
                file_content = file.read()
                if result["RequiresAuth"]:
                    await self.request_async(
                        "PUT", write_uri, headers=headers, content=file_content
                    )
                else:
                    await self.custom_client_async.put(
                        write_uri, headers=headers, content=file_content
                    )

    @traced(name="buckets_retrieve", run_type="uipath")
    @infer_bindings(resource_type="bucket")
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

    @traced(name="buckets_retrieve", run_type="uipath")
    @infer_bindings(resource_type="bucket")
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
        bucket_id: int,
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
        bucket_id: int,
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
