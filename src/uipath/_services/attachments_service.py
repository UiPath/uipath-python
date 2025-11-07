import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union, overload

import httpx

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
from .._utils._ssl_context import get_httpx_client_kwargs
from .._utils.constants import TEMP_ATTACHMENTS_FOLDER
from ..tracing import traced
from ._base_service import BaseService


def _upload_attachment_input_processor(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Process attachment upload inputs to avoid logging large content."""
    processed_inputs = inputs.copy()
    if "source_path" in processed_inputs:
        processed_inputs["source_path"] = f"<File at {processed_inputs['source_path']}>"
    if "content" in processed_inputs:
        if isinstance(processed_inputs["content"], str):
            processed_inputs["content"] = "<Redacted String Content>"
        else:
            processed_inputs["content"] = "<Redacted Binary Content>"
    return processed_inputs


class AttachmentsService(FolderContext, BaseService):
    """Service for managing UiPath attachments.

    Attachments allow you to upload and download files to be used within UiPath
    processes, actions, and other UiPath services.

    Reference: https://docs.uipath.com/orchestrator/reference/api-attachments
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._temp_dir = os.path.join(tempfile.gettempdir(), TEMP_ATTACHMENTS_FOLDER)

    @traced(name="attachments_download", run_type="uipath")
    def download(
        self,
        *,
        key: uuid.UUID,
        destination_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> str:
        """Download an attachment.

        This method downloads an attachment from UiPath to a local file.
        If the attachment is not found in UiPath (404 error), it will check
        for a local file in the temporary directory that matches the UUID.

        Note:
            The local file fallback functionality is intended for local development
            and debugging purposes only.

        Args:
            key (uuid.UUID): The key of the attachment to download.
            destination_path (str): The local path where the attachment will be saved.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            str: The name of the downloaded attachment.

        Raises:
            Exception: If the download fails and no local file is found.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            attachment_name = client.attachments.download(
                key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
                destination_path="path/to/save/document.pdf"
            )
            print(f"Downloaded attachment: {attachment_name}")
            ```
        """
        try:
            spec = self._retrieve_download_uri_spec(
                key=key,
                folder_key=folder_key,
                folder_path=folder_path,
            )

            result = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()

            # Get the attachment name
            attachment_name = result["Name"]

            download_uri = result["BlobFileAccess"]["Uri"]
            headers = {
                key: value
                for key, value in zip(
                    result["BlobFileAccess"]["Headers"]["Keys"],
                    result["BlobFileAccess"]["Headers"]["Values"],
                    strict=False,
                )
            }

            with open(destination_path, "wb") as file:
                if result["BlobFileAccess"]["RequiresAuth"]:
                    response = self.request(
                        "GET", download_uri, headers=headers, stream=True
                    )
                    for chunk in response.iter_bytes(chunk_size=8192):
                        file.write(chunk)
                else:
                    with httpx.Client(**get_httpx_client_kwargs()) as client:
                        with client.stream(
                            "GET", download_uri, headers=headers
                        ) as response:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                file.write(chunk)

            return attachment_name
        except Exception as e:
            # If not found in UiPath, check local storage
            if "404" in str(e):
                # Check if file exists in temp directory
                if os.path.exists(self._temp_dir):
                    # Look for any file starting with our UUID
                    pattern = f"{key}_*"
                    matching_files = list(Path(self._temp_dir).glob(pattern))

                    if matching_files:
                        # Get the full filename
                        local_file = matching_files[0]

                        # Extract the original name from the filename (part after UUID_)
                        file_name = os.path.basename(local_file)
                        original_name = file_name[len(f"{key}_") :]

                        # Copy the file to the destination
                        shutil.copy2(local_file, destination_path)

                        return original_name

            # Re-raise the original exception if we can't find it locally
            raise Exception(
                f"Attachment with key {key} not found in UiPath or local storage"
            ) from e

    @traced(name="attachments_download", run_type="uipath")
    async def download_async(
        self,
        *,
        key: uuid.UUID,
        destination_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> str:
        """Download an attachment asynchronously.

        This method asynchronously downloads an attachment from UiPath to a local file.
        If the attachment is not found in UiPath (404 error), it will check
        for a local file in the temporary directory that matches the UUID.

        Note:
            The local file fallback functionality is intended for local development
            and debugging purposes only.

        Args:
            key (uuid.UUID): The key of the attachment to download.
            destination_path (str): The local path where the attachment will be saved.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            str: The name of the downloaded attachment.

        Raises:
            Exception: If the download fails and no local file is found.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            client = UiPath()

            async def main():
                attachment_name = await client.attachments.download_async(
                    key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
                    destination_path="path/to/save/document.pdf"
                )
                print(f"Downloaded attachment: {attachment_name}")
            ```
        """
        try:
            spec = self._retrieve_download_uri_spec(
                key=key,
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

            # Get the attachment name
            attachment_name = result["Name"]

            download_uri = result["BlobFileAccess"]["Uri"]
            headers = {
                key: value
                for key, value in zip(
                    result["BlobFileAccess"]["Headers"]["Keys"],
                    result["BlobFileAccess"]["Headers"]["Values"],
                    strict=False,
                )
            }

            with open(destination_path, "wb") as file:
                if result["BlobFileAccess"]["RequiresAuth"]:
                    response = await self.request_async(
                        "GET", download_uri, headers=headers, stream=True
                    )
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        file.write(chunk)
                else:
                    async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
                        async with client.stream(
                            "GET", download_uri, headers=headers
                        ) as response:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                file.write(chunk)

            return attachment_name
        except Exception as e:
            # If not found in UiPath, check local storage
            if "404" in str(e):
                # Check if file exists in temp directory
                if os.path.exists(self._temp_dir):
                    # Look for any file starting with our UUID
                    pattern = f"{key}_*"
                    matching_files = list(Path(self._temp_dir).glob(pattern))

                    if matching_files:
                        # Get the full filename
                        local_file = matching_files[0]

                        # Extract the original name from the filename (part after UUID_)
                        file_name = os.path.basename(local_file)
                        original_name = file_name[len(f"{key}_") :]

                        # Copy the file to the destination
                        shutil.copy2(local_file, destination_path)

                        return original_name

            # Re-raise the original exception if we can't find it locally
            raise Exception(
                f"Attachment with key {key} not found in UiPath or local storage"
            ) from e

    @overload
    def upload(
        self,
        *,
        name: str,
        content: Union[str, bytes],
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID: ...

    @overload
    def upload(
        self,
        *,
        name: str,
        source_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID: ...

    @traced(
        name="attachments_upload",
        run_type="uipath",
        input_processor=_upload_attachment_input_processor,
    )
    def upload(
        self,
        *,
        name: str,
        content: Optional[Union[str, bytes]] = None,
        source_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID:
        """Upload a file or content to UiPath as an attachment.

        This method uploads content to UiPath and makes it available as an attachment.
        You can either provide a file path or content in memory.

        Args:
            name (str): The name of the attachment file.
            content (Optional[Union[str, bytes]]): The content to upload (string or bytes).
            source_path (Optional[str]): The local path of the file to upload.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            uuid.UUID: The UUID of the created attachment.

        Raises:
            ValueError: If neither content nor source_path is provided, or if both are provided.
            Exception: If the upload fails.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            # Upload a file from disk
            attachment_key = client.attachments.upload(
                name="my-document.pdf",
                source_path="path/to/local/document.pdf",
            )
            print(f"Uploaded attachment with key: {attachment_key}")

            # Upload content from memory
            attachment_key = client.attachments.upload(
                name="notes.txt",
                content="This is a text file content",
            )
            print(f"Uploaded attachment with key: {attachment_key}")
            ```
        """
        # Validate input parameters
        if not (content or source_path):
            raise ValueError("Content or source_path is required")
        if content and source_path:
            raise ValueError("Content and source_path are mutually exclusive")

        spec = self._create_attachment_and_retrieve_upload_uri_spec(
            name=name,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        result = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
            json=spec.json,
        ).json()

        # Get the ID from the response and convert to UUID
        attachment_key = uuid.UUID(result["Id"])

        upload_uri = result["BlobFileAccess"]["Uri"]
        headers = {
            key: value
            for key, value in zip(
                result["BlobFileAccess"]["Headers"]["Keys"],
                result["BlobFileAccess"]["Headers"]["Values"],
                strict=False,
            )
        }

        if source_path:
            # Upload from file
            with open(source_path, "rb") as file:
                file_content = file.read()
                if result["BlobFileAccess"]["RequiresAuth"]:
                    self.request(
                        "PUT", upload_uri, headers=headers, content=file_content
                    )
                else:
                    with httpx.Client(**get_httpx_client_kwargs()) as client:
                        client.put(upload_uri, headers=headers, content=file_content)
        else:
            # Upload from memory
            # Convert string to bytes if needed
            if isinstance(content, str):
                content = content.encode("utf-8")

            if result["BlobFileAccess"]["RequiresAuth"]:
                self.request("PUT", upload_uri, headers=headers, content=content)
            else:
                with httpx.Client(**get_httpx_client_kwargs()) as client:
                    client.put(upload_uri, headers=headers, content=content)

        return attachment_key

    @overload
    async def upload_async(
        self,
        *,
        name: str,
        content: Union[str, bytes],
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID: ...

    @overload
    async def upload_async(
        self,
        *,
        name: str,
        source_path: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID: ...

    @traced(
        name="attachments_upload",
        run_type="uipath",
        input_processor=_upload_attachment_input_processor,
    )
    async def upload_async(
        self,
        *,
        name: str,
        content: Optional[Union[str, bytes]] = None,
        source_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID:
        """Upload a file or content to UiPath as an attachment asynchronously.

        This method asynchronously uploads content to UiPath and makes it available as an attachment.
        You can either provide a file path or content in memory.

        Args:
            name (str): The name of the attachment file.
            content (Optional[Union[str, bytes]]): The content to upload (string or bytes).
            source_path (Optional[str]): The local path of the file to upload.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            uuid.UUID: The UUID of the created attachment.

        Raises:
            ValueError: If neither content nor source_path is provided, or if both are provided.
            Exception: If the upload fails.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            client = UiPath()

            async def main():
                # Upload a file from disk
                attachment_key = await client.attachments.upload_async(
                    name="my-document.pdf",
                    source_path="path/to/local/document.pdf",
                )
                print(f"Uploaded attachment with key: {attachment_key}")

                # Upload content from memory
                attachment_key = await client.attachments.upload_async(
                    name="notes.txt",
                    content="This is a text file content",
                )
                print(f"Uploaded attachment with key: {attachment_key}")
            ```
        """
        # Validate input parameters
        if not (content or source_path):
            raise ValueError("Content or source_path is required")
        if content and source_path:
            raise ValueError("Content and source_path are mutually exclusive")

        spec = self._create_attachment_and_retrieve_upload_uri_spec(
            name=name,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        result = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
                json=spec.json,
            )
        ).json()

        # Get the ID from the response and convert to UUID
        attachment_key = uuid.UUID(result["Id"])

        upload_uri = result["BlobFileAccess"]["Uri"]
        headers = {
            key: value
            for key, value in zip(
                result["BlobFileAccess"]["Headers"]["Keys"],
                result["BlobFileAccess"]["Headers"]["Values"],
                strict=False,
            )
        }

        if source_path:
            # Upload from file
            with open(source_path, "rb") as file:
                file_content = file.read()
                if result["BlobFileAccess"]["RequiresAuth"]:
                    await self.request_async(
                        "PUT", upload_uri, headers=headers, content=file_content
                    )
                else:
                    with httpx.Client(**get_httpx_client_kwargs()) as client:
                        client.put(upload_uri, headers=headers, content=file_content)
        else:
            # Upload from memory
            # Convert string to bytes if needed
            if isinstance(content, str):
                content = content.encode("utf-8")

            if result["BlobFileAccess"]["RequiresAuth"]:
                await self.request_async(
                    "PUT", upload_uri, headers=headers, content=content
                )
            else:
                with httpx.Client(**get_httpx_client_kwargs()) as client:
                    client.put(upload_uri, headers=headers, content=content)

        return attachment_key

    @traced(name="attachments_delete", run_type="uipath")
    def delete(
        self,
        *,
        key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Delete an attachment.

        This method deletes an attachment from UiPath.
        If the attachment is not found in UiPath (404 error), it will check
        for a local file in the temporary directory that matches the UUID.

        Note:
            The local file fallback functionality is intended for local development
            and debugging purposes only.

        Args:
            key (uuid.UUID): The key of the attachment to delete.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Raises:
            Exception: If the deletion fails and no local file is found.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            client.attachments.delete(
                key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
            )
            print("Attachment deleted successfully")
            ```
        """
        try:
            spec = self._delete_attachment_spec(
                key=key,
                folder_key=folder_key,
                folder_path=folder_path,
            )

            self.request(
                spec.method,
                url=spec.endpoint,
                headers=spec.headers,
            )
        except Exception as e:
            # If not found in UiPath, check local storage
            if "404" in str(e):
                # Check if file exists in temp directory
                if os.path.exists(self._temp_dir):
                    # Look for any file starting with our UUID
                    pattern = f"{key}_*"
                    matching_files = list(Path(self._temp_dir).glob(pattern))

                    if matching_files:
                        # Delete all matching files
                        for file_path in matching_files:
                            os.remove(file_path)
                        return

            # Re-raise the original exception if we can't find it locally
            raise Exception(
                f"Attachment with key {key} not found in UiPath or local storage"
            ) from e

    @traced(name="attachments_delete", run_type="uipath")
    async def delete_async(
        self,
        *,
        key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Delete an attachment asynchronously.

        This method asynchronously deletes an attachment from UiPath.
        If the attachment is not found in UiPath (404 error), it will check
        for a local file in the temporary directory that matches the UUID.

        Note:
            The local file fallback functionality is intended for local development
            and debugging purposes only.

        Args:
            key (uuid.UUID): The key of the attachment to delete.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Raises:
            Exception: If the deletion fails and no local file is found.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            client = UiPath()

            async def main():
                await client.attachments.delete_async(
                    key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
                )
                print("Attachment deleted successfully")
            ```
        """
        try:
            spec = self._delete_attachment_spec(
                key=key,
                folder_key=folder_key,
                folder_path=folder_path,
            )

            await self.request_async(
                spec.method,
                url=spec.endpoint,
                headers=spec.headers,
            )
        except Exception as e:
            # If not found in UiPath, check local storage
            if "404" in str(e):
                # Check if file exists in temp directory
                if os.path.exists(self._temp_dir):
                    # Look for any file starting with our UUID
                    pattern = f"{key}_*"
                    matching_files = list(Path(self._temp_dir).glob(pattern))

                    if matching_files:
                        # Delete all matching files
                        for file_path in matching_files:
                            os.remove(file_path)
                        return

            # Re-raise the original exception if we can't find it locally
            raise Exception(
                f"Attachment with key {key} not found in UiPath or local storage"
            ) from e

    @property
    def custom_headers(self) -> Dict[str, str]:
        """Return custom headers for API requests."""
        return self.folder_headers

    def _create_attachment_and_retrieve_upload_uri_spec(
        self,
        name: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/orchestrator_/odata/Attachments"),
            json={
                "Name": name,
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_download_uri_spec(
        self,
        key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/orchestrator_/odata/Attachments({key})"),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _delete_attachment_spec(
        self,
        key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"/orchestrator_/odata/Attachments({key})"),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
