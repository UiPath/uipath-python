import asyncio
import mimetypes
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Union

import httpx

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, resource_override
from .._utils._ssl_context import get_httpx_client_kwargs
from ..models import Bucket, BucketFile
from ..tracing import traced
from ._base_service import BaseService


class BucketsService(FolderContext, BaseService):
    """Service for managing UiPath storage buckets.

    Buckets are cloud storage containers that can be used to store and manage files
    used by automation processes.
    """

    _GET_FILES_PAGE_SIZE = 500  # OData GetFiles pagination page size

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

    @traced(name="buckets_delete", run_type="uipath")
    @resource_override(resource_type="bucket")
    def delete(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete a bucket.

        Args:
            name: Bucket name
            key: Bucket identifier (UUID)
            folder_path: Folder path
            folder_key: Folder key

        Raises:
            LookupError: If bucket is not found

        Examples:
            >>> sdk.buckets.delete(name="old-storage")
            >>> sdk.buckets.delete(key="abc-123-def")
        """
        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        self.request(
            "DELETE",
            url=f"/orchestrator_/odata/Buckets({bucket.id})",
            headers={**self.folder_headers},
        )

    @traced(name="buckets_delete", run_type="uipath")
    @resource_override(resource_type="bucket")
    async def delete_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Async version of delete()."""
        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        await self.request_async(
            "DELETE",
            url=f"/orchestrator_/odata/Buckets({bucket.id})",
            headers={**self.folder_headers},
        )

    @traced(name="buckets_download", run_type="uipath")
    @resource_override(resource_type="bucket")
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
            if result["RequiresAuth"]:
                file_content = self.request("GET", read_uri, headers=headers).content
            else:
                file_content = self.custom_client.get(read_uri, headers=headers).content
            file.write(file_content)

    @traced(name="buckets_download", run_type="uipath")
    @resource_override(resource_type="bucket")
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
    @resource_override(resource_type="bucket")
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
    @resource_override(resource_type="bucket")
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
    @resource_override(resource_type="bucket")
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
            try:
                response = self.request(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                ).json()
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
    @resource_override(resource_type="bucket")
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
            try:
                response = (
                    await self.request_async(
                        spec.method,
                        url=spec.endpoint,
                        params=spec.params,
                        headers=spec.headers,
                    )
                ).json()
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
    @resource_override(resource_type="bucket")
    def list_files(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        prefix: str = "",
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Iterator[BucketFile]:
        """List files in a bucket.

        Args:
            name: Bucket name
            key: Bucket identifier
            prefix: Filter files by prefix
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            Iterator[BucketFile]: Iterator of files in the bucket

        Note:
            Returns an iterator for memory efficiency. Use list() to materialize all results:
            files = list(sdk.buckets.list_files(name="my-storage"))

            This method automatically handles pagination, fetching up to 500 files per request.

        Examples:
            >>> for file in sdk.buckets.list_files(name="my-storage"):
            ...     print(file.path)
            >>> files = list(sdk.buckets.list_files(name="my-storage", prefix="data/"))
        """
        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        continuation_token: Optional[str] = None

        while True:
            spec = self._list_files_spec(
                bucket.id,
                prefix,
                continuation_token=continuation_token,
                folder_key=folder_key,
                folder_path=folder_path,
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()

            items = response.get("items", [])
            for item in items:
                yield BucketFile.model_validate(item)

            continuation_token = response.get("continuationToken")
            if not continuation_token:
                break

    @traced(name="buckets_list_files", run_type="uipath")
    @resource_override(resource_type="bucket")
    async def list_files_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        prefix: str = "",
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> AsyncIterator[BucketFile]:
        """List files in a bucket asynchronously.

        Args:
            name: Bucket name
            key: Bucket identifier
            prefix: Filter files by prefix
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            AsyncIterator[BucketFile]: Async iterator of files in the bucket

        Note:
            Returns an async iterator for memory efficiency. Use list comprehension to materialize:
            files = [f async for f in sdk.buckets.list_files_async(name="my-storage")]

            This method automatically handles pagination, fetching up to 500 files per request.

        Examples:
            >>> async for file in sdk.buckets.list_files_async(name="my-storage"):
            ...     print(file.path)
            >>> files = [f async for f in sdk.buckets.list_files_async(name="my-storage", prefix="data/")]
        """
        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        continuation_token: Optional[str] = None

        while True:
            spec = self._list_files_spec(
                bucket.id,
                prefix,
                continuation_token=continuation_token,
                folder_key=folder_key,
                folder_path=folder_path,
            )
            response = (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                )
            ).json()

            items = response.get("items", [])
            for item in items:
                yield BucketFile.model_validate(item)

            continuation_token = response.get("continuationToken")
            if not continuation_token:
                break

    @traced(name="buckets_exists_file", run_type="uipath")
    @resource_override(resource_type="bucket")
    def exists_file(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        blob_file_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Check if a file exists in a bucket.

        Args:
            name: Bucket name
            key: Bucket identifier
            blob_file_path: Path to the file in the bucket (cannot be empty)
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            bool: True if file exists, False otherwise

        Note:
            This method uses short-circuit iteration to stop at the first match,
            making it memory-efficient even for large buckets. It will raise
            LookupError if the bucket itself doesn't exist.

        Raises:
            ValueError: If blob_file_path is empty or whitespace-only
            LookupError: If bucket is not found

        Examples:
            >>> if sdk.buckets.exists_file(name="my-storage", blob_file_path="data/file.csv"):
            ...     print("File exists")
            >>> # Check in specific folder
            >>> exists = sdk.buckets.exists_file(
            ...     name="my-storage",
            ...     blob_file_path="reports/2024/summary.pdf",
            ...     folder_path="Production"
            ... )
        """
        if not blob_file_path or not blob_file_path.strip():
            raise ValueError("blob_file_path cannot be empty or whitespace-only")

        normalized_target = (
            blob_file_path if blob_file_path.startswith("/") else f"/{blob_file_path}"
        )
        for file in self.list_files(
            name=name,
            key=key,
            prefix=blob_file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        ):
            if file.path == normalized_target:
                return True
        return False

    @traced(name="buckets_exists_file", run_type="uipath")
    @resource_override(resource_type="bucket")
    async def exists_file_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        blob_file_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Async version of exists_file().

        Args:
            name: Bucket name
            key: Bucket identifier
            blob_file_path: Path to the file in the bucket (cannot be empty)
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            bool: True if file exists, False otherwise

        Raises:
            ValueError: If blob_file_path is empty or whitespace-only
            LookupError: If bucket is not found

        Examples:
            >>> if await sdk.buckets.exists_file_async(name="my-storage", blob_file_path="data/file.csv"):
            ...     print("File exists")
        """
        if not blob_file_path or not blob_file_path.strip():
            raise ValueError("blob_file_path cannot be empty or whitespace-only")

        normalized_target = (
            blob_file_path if blob_file_path.startswith("/") else f"/{blob_file_path}"
        )
        async for file in self.list_files_async(
            name=name,
            key=key,
            prefix=blob_file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        ):
            if file.path == normalized_target:
                return True
        return False

    @traced(name="buckets_delete_file", run_type="uipath")
    @resource_override(resource_type="bucket")
    def delete_file(
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
            >>> sdk.buckets.delete_file(name="my-storage", blob_file_path="data/file.txt")
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

    @traced(name="buckets_delete_file", run_type="uipath")
    @resource_override(resource_type="bucket")
    async def delete_file_async(
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
            >>> await sdk.buckets.delete_file_async(name="my-storage", blob_file_path="data/file.txt")
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

    @traced(name="buckets_get_files", run_type="uipath")
    @resource_override(resource_type="bucket")
    def get_files(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        prefix: str = "",
        recursive: bool = False,
        file_name_glob: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Iterator[BucketFile]:
        """Get files using OData GetFiles API (Studio-compatible).

        This method uses the GetFiles API which is used by UiPath Studio activities.
        Use this when you need:
        - Recursive directory traversal
        - Glob pattern filtering (e.g., "*.pdf")
        - Compatibility with Studio activity behavior

        Args:
            name: Bucket name
            key: Bucket identifier
            prefix: Directory path to filter files (default: root)
            recursive: Recurse subdirectories for flat view (default: False)
            file_name_glob: File filter pattern (e.g., "*.pdf", "data_*.csv")
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            Iterator[BucketFile]: Iterator of files matching criteria

        Raises:
            ValueError: If neither name nor key is provided
            LookupError: If bucket not found
            Exception: For API errors or invalid responses

        Note:
            For large buckets with 10,000+ files, consider using list_files()
            which uses more efficient cursor-based pagination.

        Examples:
            >>> # Get all PDF files recursively
            >>> for file in sdk.buckets.get_files(
            ...     name="my-storage",
            ...     recursive=True,
            ...     file_name_glob="*.pdf"
            ... ):
            ...     print(f"{file.path} - {file.size} bytes")
            >>>
            >>> # Get files in specific directory
            >>> files = list(sdk.buckets.get_files(
            ...     name="my-storage",
            ...     prefix="reports/"
            ... ))
        """
        if not (name or key):
            raise ValueError("Must specify either bucket name or key")

        if file_name_glob is not None and not file_name_glob.strip():
            raise ValueError("file_name_glob cannot be empty")

        bucket = self.retrieve(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        skip = 0
        top = self._GET_FILES_PAGE_SIZE

        while True:
            spec = self._get_files_spec(
                bucket.id,
                prefix=prefix,
                recursive=recursive,
                file_name_glob=file_name_glob,
                skip=skip,
                top=top,
                folder_key=folder_key,
                folder_path=folder_path,
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
                if not item.get("IsDirectory", False):
                    try:
                        yield BucketFile.model_validate(item)
                    except Exception as e:
                        raise ValueError(
                            f"Failed to parse file entry: {e}. Item: {item}"
                        ) from e

            if len(items) < top:
                break

            skip += top

    @traced(name="buckets_get_files", run_type="uipath")
    @resource_override(resource_type="bucket")
    async def get_files_async(
        self,
        *,
        name: Optional[str] = None,
        key: Optional[str] = None,
        prefix: str = "",
        recursive: bool = False,
        file_name_glob: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> AsyncIterator[BucketFile]:
        """Async version of get_files().

        See get_files() for detailed documentation.

        Examples:
            >>> async for file in sdk.buckets.get_files_async(
            ...     name="my-storage",
            ...     recursive=True,
            ...     file_name_glob="*.pdf"
            ... ):
            ...     print(file.path)
        """
        if not (name or key):
            raise ValueError("Must specify either bucket name or key")

        if file_name_glob is not None and not file_name_glob.strip():
            raise ValueError("file_name_glob cannot be empty")

        bucket = await self.retrieve_async(
            name=name, key=key, folder_key=folder_key, folder_path=folder_path
        )

        skip = 0
        top = self._GET_FILES_PAGE_SIZE

        while True:
            spec = self._get_files_spec(
                bucket.id,
                prefix=prefix,
                recursive=recursive,
                file_name_glob=file_name_glob,
                skip=skip,
                top=top,
                folder_key=folder_key,
                folder_path=folder_path,
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
                if not item.get("IsDirectory", False):
                    try:
                        yield BucketFile.model_validate(item)
                    except Exception as e:
                        raise ValueError(
                            f"Failed to parse file entry: {e}. Item: {item}"
                        ) from e

            if len(items) < top:
                break

            skip += top

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
            escaped_name = name.replace("'", "''")
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
            "Identifier": identifier,
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
        continuation_token: Optional[str] = None,
        take_hint: int = 500,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        """Build REST API request for listing files in a bucket.

        Uses the /api/Buckets/{id}/ListFiles endpoint which supports pagination.

        Args:
            bucket_id: The bucket ID
            prefix: Path prefix for filtering
            continuation_token: Token for pagination
            take_hint: Minimum number of files to return (default 500, max 1000)
            folder_key: Folder key
            folder_path: Folder path
        """
        params: Dict[str, Any] = {}
        if prefix:
            params["prefix"] = prefix
        if continuation_token:
            params["continuationToken"] = continuation_token
        if take_hint:
            params["takeHint"] = take_hint

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/api/Buckets/{bucket_id}/ListFiles"),
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

    def _get_files_spec(
        self,
        bucket_id: int,
        prefix: str = "",
        recursive: bool = False,
        file_name_glob: Optional[str] = None,
        skip: int = 0,
        top: int = 500,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        """Build OData request for GetFiles endpoint.

        Args:
            bucket_id: Bucket ID
            prefix: Directory path prefix
            recursive: Recurse subdirectories
            file_name_glob: File name filter pattern
            skip: Number of items to skip (pagination)
            top: Number of items to return (pagination)
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            RequestSpec: OData request specification
        """
        params: Dict[str, Any] = {}

        params["directory"] = "/" if not prefix else prefix

        if recursive:
            params["recursive"] = "true"

        if file_name_glob:
            params["fileNameGlob"] = file_name_glob

        if skip > 0:
            params["$skip"] = skip
        params["$top"] = top

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Buckets({bucket_id})/UiPath.Server.Configuration.OData.GetFiles"
            ),
            params=params,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
