import asyncio
import mimetypes
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union

import httpx

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, infer_bindings
from .._utils._ssl_context import get_httpx_client_kwargs
from ..models import Bucket, BucketFile
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

    @traced(name="buckets_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Iterator[Bucket]:
        """List buckets with auto-pagination.

        Args:
            folder_path: Folder path to filter buckets
            folder_key: Folder key (mutually exclusive with folder_path)
            name: Filter by bucket name (contains match)

        Yields:
            Bucket: Bucket resource instances

        Examples:
            >>> # List all buckets
            >>> for bucket in sdk.buckets.list():
            ...     print(bucket.name)
            >>>
            >>> # Filter by folder
            >>> for bucket in sdk.buckets.list(folder_path="Production"):
            ...     print(bucket.name)
            >>>
            >>> # Filter by name
            >>> for bucket in sdk.buckets.list(name="invoice"):
            ...     print(bucket.name)
        """
        skip = 0
        top = 100

        while True:
            spec = self._list_spec(
                folder_path=folder_path,
                folder_key=folder_key,
                name=name,
                skip=skip,
                top=top,
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                bucket = Bucket.model_validate(item)
                yield bucket

            # Check if more pages available
            if len(items) < top:
                break

            skip += top

    @traced(name="buckets_list", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
    ) -> AsyncIterator[Bucket]:
        """Async version of list() with auto-pagination."""
        skip = 0
        top = 50

        while True:
            spec = self._list_spec(
                folder_path=folder_path,
                folder_key=folder_key,
                name=name,
                skip=skip,
                top=top,
            )
            response = (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                )
            ).json()

            items = response.get("value", [])
            if not items:
                break

            for item in items:
                bucket = Bucket.model_validate(item)
                yield bucket

            if len(items) < top:
                break

            skip += top

    @traced(name="buckets_exists", run_type="uipath")
    def exists(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Check if bucket exists.

        Args:
            name: Bucket name
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            bool: True if bucket exists

        Examples:
            >>> if sdk.buckets.exists("my-storage"):
            ...     print("Bucket found")
        """
        try:
            self.retrieve(name=name, folder_key=folder_key, folder_path=folder_path)
            return True
        except LookupError:
            return False

    @traced(name="buckets_exists", run_type="uipath")
    async def exists_async(
        self,
        name: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Async version of exists()."""
        try:
            await self.retrieve_async(
                name=name, folder_key=folder_key, folder_path=folder_path
            )
            return True
        except LookupError:
            return False

    @traced(name="buckets_create", run_type="uipath")
    def create(
        self,
        name: str,
        *,
        description: Optional[str] = None,
        identifier: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Bucket:
        """Create a new bucket.

        Args:
            name: Bucket name (must be unique within folder)
            description: Optional description
            identifier: UUID identifier (auto-generated if not provided)
            folder_path: Folder to create bucket in
            folder_key: Folder key

        Returns:
            Bucket: Newly created bucket resource

        Raises:
            Exception: If bucket creation fails

        Examples:
            >>> bucket = sdk.buckets.create("my-storage")
            >>> bucket = sdk.buckets.create(
            ...     "data-storage",
            ...     description="Production data"
            ... )
        """
        spec = self._create_spec(
            name=name,
            description=description,
            identifier=identifier or str(uuid.uuid4()),
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        ).json()

        bucket = Bucket.model_validate(response)
        return bucket

    @traced(name="buckets_create", run_type="uipath")
    async def create_async(
        self,
        name: str,
        *,
        description: Optional[str] = None,
        identifier: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Bucket:
        """Async version of create()."""
        spec = self._create_spec(
            name=name,
            description=description,
            identifier=identifier or str(uuid.uuid4()),
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
        ).json()

        bucket = Bucket.model_validate(response)
        return bucket

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

        # the self.request adds auth bearer token
        if result["RequiresAuth"]:
            file_content = (
                await self.request_async("GET", read_uri, headers=headers)
            ).content
        else:
            file_content = (
                await self.custom_client_async.get(read_uri, headers=headers)
            ).content

        await asyncio.to_thread(Path(destination_path).write_bytes, file_content)

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
            file_content = await asyncio.to_thread(Path(source_path).read_bytes)
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
            Bucket: The bucket resource instance.

        Raises:
            ValueError: If neither bucket key nor bucket name is provided.
            Exception: If the bucket with the specified name is not found.

        Examples:
            >>> bucket = sdk.buckets.retrieve(name="my-storage")
            >>> print(bucket.name, bucket.identifier)
        """
        if not (key or name):
            raise ValueError("Must specify a bucket name or bucket key")

        if key:
            spec = self._retrieve_by_key_spec(
                key, folder_key=folder_key, folder_path=folder_path
            )
            # GetByKey may return single object or OData collection format
            try:
                response = self.request(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                ).json()
                # Handle both direct object and OData collection wrapper
                if "value" in response:
                    items = response.get("value", [])
                    if not items:
                        raise LookupError(f"Bucket with key '{key}' not found")
                    bucket_data = items[0]
                else:
                    bucket_data = response
            except (KeyError, IndexError) as e:
                raise LookupError(f"Bucket with key '{key}' not found") from e
        else:
            spec = self._retrieve_spec(
                name,  # type: ignore
                folder_key=folder_key,
                folder_path=folder_path,
            )
            # OData query returns collection in "value" array
            try:
                response = self.request(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                ).json()
                items = response.get("value", [])
                if not items:
                    raise LookupError(f"Bucket with name '{name}' not found")
                bucket_data = items[0]
            except (KeyError, IndexError) as e:
                raise LookupError(f"Bucket with name '{name}' not found") from e

        bucket = Bucket.model_validate(bucket_data)
        return bucket

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
            Bucket: The bucket resource instance.

        Raises:
            ValueError: If neither bucket key nor bucket name is provided.
            Exception: If the bucket with the specified name is not found.

        Examples:
            >>> bucket = await sdk.buckets.retrieve_async(name="my-storage")
            >>> print(bucket.name, bucket.identifier)
        """
        if not (key or name):
            raise ValueError("Must specify a bucket name or bucket key")

        if key:
            spec = self._retrieve_by_key_spec(
                key, folder_key=folder_key, folder_path=folder_path
            )
            # GetByKey may return single object or OData collection format
            try:
                response = (
                    await self.request_async(
                        spec.method,
                        url=spec.endpoint,
                        params=spec.params,
                        headers=spec.headers,
                    )
                ).json()
                # Handle both direct object and OData collection wrapper
                if "value" in response:
                    items = response.get("value", [])
                    if not items:
                        raise LookupError(f"Bucket with key '{key}' not found")
                    bucket_data = items[0]
                else:
                    bucket_data = response
            except (KeyError, IndexError) as e:
                raise LookupError(f"Bucket with key '{key}' not found") from e
        else:
            spec = self._retrieve_spec(
                name,  # type: ignore
                folder_key=folder_key,
                folder_path=folder_path,
            )
            # OData query returns collection in "value" array
            try:
                response = (
                    await self.request_async(
                        spec.method,
                        url=spec.endpoint,
                        params=spec.params,
                        headers=spec.headers,
                    )
                ).json()
                items = response.get("value", [])
                if not items:
                    raise LookupError(f"Bucket with name '{name}' not found")
                bucket_data = items[0]
            except (KeyError, IndexError) as e:
                raise LookupError(f"Bucket with name '{name}' not found") from e

        bucket = Bucket.model_validate(bucket_data)
        return bucket

    @traced(name="buckets_list_files", run_type="uipath")
    @infer_bindings(resource_type="bucket")
    def list_files(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        prefix: str = "",
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[BucketFile]:
        """List files in a bucket.

        Args:
            name: Bucket name
            key: Bucket identifier
            prefix: Filter files by prefix
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            List[BucketFile]: List of files in the bucket

        Examples:
            >>> files = sdk.buckets.list_files(name="my-storage")
            >>> files = sdk.buckets.list_files(name="my-storage", prefix="data/")
        """
        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )
        spec = self._list_files_spec(
            bucket.id, prefix, folder_key=folder_key, folder_path=folder_path
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()

        items = response.get("value", [])
        return [BucketFile.model_validate(item) for item in items]

    @traced(name="buckets_list_files", run_type="uipath")
    @infer_bindings(resource_type="bucket")
    async def list_files_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        prefix: str = "",
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[BucketFile]:
        """List files in a bucket asynchronously.

        Args:
            name: Bucket name
            key: Bucket identifier
            prefix: Filter files by prefix
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            List[BucketFile]: List of files in the bucket

        Examples:
            >>> files = await sdk.buckets.list_files_async(name="my-storage")
            >>> files = await sdk.buckets.list_files_async(name="my-storage", prefix="data/")
        """
        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )
        spec = self._list_files_spec(
            bucket.id, prefix, folder_key=folder_key, folder_path=folder_path
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()

        items = response.get("value", [])
        return [BucketFile.model_validate(item) for item in items]

    @traced(name="buckets_delete", run_type="uipath")
    @infer_bindings(resource_type="bucket")
    def delete(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        blob_file_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Delete a file from a bucket.

        Args:
            name: Bucket name
            key: Bucket identifier
            blob_file_path: Path to the file in the bucket
            folder_key: Folder key
            folder_path: Folder path

        Examples:
            >>> sdk.buckets.delete(name="my-storage", blob_file_path="data/file.txt")
        """
        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )
        spec = self._delete_file_spec(
            bucket.id, blob_file_path, folder_key=folder_key, folder_path=folder_path
        )
        self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

    @traced(name="buckets_delete", run_type="uipath")
    @infer_bindings(resource_type="bucket")
    async def delete_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        blob_file_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Delete a file from a bucket asynchronously.

        Args:
            name: Bucket name
            key: Bucket identifier
            blob_file_path: Path to the file in the bucket
            folder_key: Folder key
            folder_path: Folder path

        Examples:
            >>> await sdk.buckets.delete_async(name="my-storage", blob_file_path="data/file.txt")
        """
        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )
        spec = self._delete_file_spec(
            bucket.id, blob_file_path, folder_key=folder_key, folder_path=folder_path
        )
        await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def _list_spec(
        self,
        folder_path: Optional[str],
        folder_key: Optional[str],
        name: Optional[str],
        skip: int,
        top: int,
    ) -> RequestSpec:
        """Build OData request for listing buckets."""
        filters = []
        if name:
            # Case-insensitive contains using tolower
            escaped_name = name.replace("'", "''")  # Escape single quotes
            filters.append(f"contains(tolower(Name), tolower('{escaped_name}'))")

        filter_str = " and ".join(filters) if filters else None

        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if filter_str:
            params["$filter"] = filter_str

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Buckets"),
            params=params,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _create_spec(
        self,
        name: str,
        description: Optional[str],
        identifier: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        """Build request for creating bucket."""
        body = {
            "Name": name,
            "Identifier": identifier,  # Required field (UUID)
        }
        if description:
            body["Description"] = description

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/orchestrator_/odata/Buckets"),
            json=body,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_spec(
        self,
        name: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        # Escape single quotes to prevent OData filter injection
        escaped_name = name.replace("'", "''")
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Buckets"),
            params={"$filter": f"Name eq '{escaped_name}'", "$top": 1},
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
        # Escape single quotes in the key to prevent OData injection
        escaped_key = key.replace("'", "''")
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier='{escaped_key}')"
            ),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _list_files_spec(
        self,
        bucket_id: int,
        prefix: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        """Build OData request for listing files in a bucket."""
        params: Dict[str, Any] = {}
        if prefix:
            # Escape single quotes to prevent OData filter injection
            escaped_prefix = prefix.replace("'", "''")
            params["$filter"] = f"startswith(Name, '{escaped_prefix}')"

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.Files"
            ),
            params=params,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _delete_file_spec(
        self,
        bucket_id: int,
        blob_file_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        """Build request for deleting a file from a bucket."""
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.DeleteFile"
            ),
            params={"path": blob_file_path},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
