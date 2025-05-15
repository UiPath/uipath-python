import json
import os
import uuid
from typing import TYPE_CHECKING, Any, Dict

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.attachments_service import AttachmentsService
from uipath._utils.constants import HEADER_USER_AGENT

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: "MonkeyPatch",
) -> AttachmentsService:
    """Fixture that provides a configured AttachmentsService instance for testing.

    Args:
        config: The Config fixture with test configuration settings.
        execution_context: The ExecutionContext fixture with test execution context.
        monkeypatch: PyTest MonkeyPatch fixture for environment modification.

    Returns:
        AttachmentsService: A configured instance of AttachmentsService.
    """
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return AttachmentsService(config=config, execution_context=execution_context)


@pytest.fixture
def temp_file(tmp_path: Any) -> str:
    """Creates a temporary file for testing file uploads and downloads.

    Args:
        tmp_path: PyTest fixture providing a temporary directory.

    Returns:
        str: Path to the temporary test file.
    """
    file_path = os.path.join(tmp_path, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Test content")
    return file_path


@pytest.fixture
def blob_uri_response() -> Dict[str, Any]:
    """Provides a mock response for blob access requests.

    Returns:
        Dict[str, Any]: A mock API response with blob storage access details.
    """
    return {
        "Id": "12345678-1234-1234-1234-123456789012",
        "Name": "test_file.txt",
        "BlobFileAccess": {
            "Uri": "https://test-storage.com/test-container/test-blob",
            "Headers": {
                "Keys": ["x-ms-blob-type", "Content-Type"],
                "Values": ["BlockBlob", "application/octet-stream"],
            },
            "RequiresAuth": False,
        },
    }


class TestAttachmentsService:
    """Test suite for the AttachmentsService class."""

    def test_upload_with_file_path(
        self,
        httpx_mock: HTTPXMock,
        service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        temp_file: str,
        blob_uri_response: Dict[str, Any],
    ) -> None:
        """Test uploading an attachment from a file path.

        Args:
            httpx_mock: HTTPXMock fixture for mocking HTTP requests.
            service: AttachmentsService fixture.
            base_url: Base URL fixture for the API endpoint.
            org: Organization fixture for the API path.
            tenant: Tenant fixture for the API path.
            version: Version fixture for the user agent header.
            temp_file: Temporary file fixture.
            blob_uri_response: Mock response fixture for blob operations.
        """
        # Arrange
        file_name = os.path.basename(temp_file)

        # Mock the create attachment endpoint
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments",
            method="POST",
            status_code=200,
            json=blob_uri_response,
        )

        # Mock the blob upload
        httpx_mock.add_response(
            url=blob_uri_response["BlobFileAccess"]["Uri"],
            method="PUT",
            status_code=201,
        )

        # Act
        attachment_key = service.upload(
            name=file_name,
            source_path=temp_file,
        )

        # Assert
        assert attachment_key == uuid.UUID(blob_uri_response["Id"])

        # Verify the requests
        requests = httpx_mock.get_requests()
        assert len(requests) == 2

        # Check the first request to create the attachment
        create_request = requests[0]
        assert create_request.method == "POST"
        assert (
            create_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments"
        )
        assert json.loads(create_request.content) == {"Name": file_name}
        assert HEADER_USER_AGENT in create_request.headers
        assert create_request.headers[HEADER_USER_AGENT].startswith(
            f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AttachmentsService.upload/{version}"
        )

        # Check the second request to upload the content
        upload_request = requests[1]
        assert upload_request.method == "PUT"
        assert upload_request.url == blob_uri_response["BlobFileAccess"]["Uri"]
        assert "x-ms-blob-type" in upload_request.headers
        assert upload_request.headers["x-ms-blob-type"] == "BlockBlob"

    def test_upload_with_content(
        self,
        httpx_mock: HTTPXMock,
        service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        blob_uri_response: Dict[str, Any],
    ) -> None:
        """Test uploading an attachment with in-memory content.

        Args:
            httpx_mock: HTTPXMock fixture for mocking HTTP requests.
            service: AttachmentsService fixture.
            base_url: Base URL fixture for the API endpoint.
            org: Organization fixture for the API path.
            tenant: Tenant fixture for the API path.
            version: Version fixture for the user agent header.
            blob_uri_response: Mock response fixture for blob operations.
        """
        # Arrange
        content = "Test content in memory"
        file_name = "text_content.txt"

        # Mock the create attachment endpoint
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments",
            method="POST",
            status_code=200,
            json=blob_uri_response,
        )

        # Mock the blob upload
        httpx_mock.add_response(
            url=blob_uri_response["BlobFileAccess"]["Uri"],
            method="PUT",
            status_code=201,
        )

        # Act
        attachment_key = service.upload(
            name=file_name,
            content=content,
        )

        # Assert
        assert attachment_key == uuid.UUID(blob_uri_response["Id"])

        # Verify the requests
        requests = httpx_mock.get_requests()
        assert len(requests) == 2

        # Check the first request to create the attachment
        create_request = requests[0]
        assert create_request.method == "POST"
        assert (
            create_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments"
        )
        assert json.loads(create_request.content) == {"Name": file_name}
        assert HEADER_USER_AGENT in create_request.headers

        # Check the second request to upload the content
        upload_request = requests[1]
        assert upload_request.method == "PUT"
        assert upload_request.url == blob_uri_response["BlobFileAccess"]["Uri"]
        assert "x-ms-blob-type" in upload_request.headers
        assert upload_request.headers["x-ms-blob-type"] == "BlockBlob"
        assert upload_request.content == content.encode("utf-8")

    def test_upload_validation_errors(
        self,
        service: AttachmentsService,
    ) -> None:
        """Test validation errors when uploading attachments.

        Args:
            service: AttachmentsService fixture.
        """
        # Test missing both content and source_path
        with pytest.raises(ValueError, match="Content or source_path is required"):
            service.upload(name="test.txt")  # type: ignore

        # Test providing both content and source_path
        with pytest.raises(
            ValueError, match="Content and source_path are mutually exclusive"
        ):
            service.upload(
                name="test.txt", content="test content", source_path="/path/to/file.txt"
            )  # type: ignore

    @pytest.mark.asyncio
    async def test_upload_async_with_content(
        self,
        httpx_mock: HTTPXMock,
        service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        blob_uri_response: Dict[str, Any],
    ) -> None:
        """Test asynchronously uploading an attachment with in-memory content.

        Args:
            httpx_mock: HTTPXMock fixture for mocking HTTP requests.
            service: AttachmentsService fixture.
            base_url: Base URL fixture for the API endpoint.
            org: Organization fixture for the API path.
            tenant: Tenant fixture for the API path.
            version: Version fixture for the user agent header.
            blob_uri_response: Mock response fixture for blob operations.
        """
        # Arrange
        content = "Test content in memory"
        file_name = "text_content.txt"

        # Mock the create attachment endpoint
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments",
            method="POST",
            status_code=200,
            json=blob_uri_response,
        )

        # Mock the blob upload
        httpx_mock.add_response(
            url=blob_uri_response["BlobFileAccess"]["Uri"],
            method="PUT",
            status_code=201,
        )

        # Act
        attachment_key = await service.upload_async(
            name=file_name,
            content=content,
        )

        # Assert
        assert attachment_key == uuid.UUID(blob_uri_response["Id"])

        # Verify the requests
        requests = httpx_mock.get_requests()
        assert len(requests) == 2

        # Check the first request to create the attachment
        create_request = requests[0]
        assert create_request.method == "POST"
        assert (
            create_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments"
        )
        assert HEADER_USER_AGENT in create_request.headers

    def test_download(
        self,
        httpx_mock: HTTPXMock,
        service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        tmp_path: Any,
        blob_uri_response: Dict[str, Any],
    ) -> None:
        """Test downloading an attachment.

        Args:
            httpx_mock: HTTPXMock fixture for mocking HTTP requests.
            service: AttachmentsService fixture.
            base_url: Base URL fixture for the API endpoint.
            org: Organization fixture for the API path.
            tenant: Tenant fixture for the API path.
            version: Version fixture for the user agent header.
            tmp_path: Temporary directory fixture.
            blob_uri_response: Mock response fixture for blob operations.
        """
        # Arrange
        attachment_key = uuid.UUID("12345678-1234-1234-1234-123456789012")
        destination_path = os.path.join(tmp_path, "downloaded_file.txt")
        file_content = b"Downloaded file content"
        expected_name = blob_uri_response["Name"]

        # Mock the get attachment endpoint
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            method="GET",
            status_code=200,
            json=blob_uri_response,
        )

        # Mock the blob download
        httpx_mock.add_response(
            url=blob_uri_response["BlobFileAccess"]["Uri"],
            method="GET",
            status_code=200,
            content=file_content,
        )

        # Act
        result = service.download(
            key=attachment_key,
            destination_path=destination_path,
        )

        # Assert
        assert result == expected_name
        assert os.path.exists(destination_path)
        with open(destination_path, "rb") as f:
            assert f.read() == file_content

        # Verify the requests
        requests = httpx_mock.get_requests()
        assert len(requests) == 2

        # Check the first request to get the attachment metadata
        get_request = requests[0]
        assert get_request.method == "GET"
        assert (
            get_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})"
        )
        assert HEADER_USER_AGENT in get_request.headers

        # Check the second request to download the content
        download_request = requests[1]
        assert download_request.method == "GET"
        assert download_request.url == blob_uri_response["BlobFileAccess"]["Uri"]

    @pytest.mark.asyncio
    async def test_download_async(
        self,
        httpx_mock: HTTPXMock,
        service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        tmp_path: Any,
        blob_uri_response: Dict[str, Any],
    ) -> None:
        """Test asynchronously downloading an attachment.

        Args:
            httpx_mock: HTTPXMock fixture for mocking HTTP requests.
            service: AttachmentsService fixture.
            base_url: Base URL fixture for the API endpoint.
            org: Organization fixture for the API path.
            tenant: Tenant fixture for the API path.
            version: Version fixture for the user agent header.
            tmp_path: Temporary directory fixture.
            blob_uri_response: Mock response fixture for blob operations.
        """
        # Arrange
        attachment_key = uuid.UUID("12345678-1234-1234-1234-123456789012")
        destination_path = os.path.join(tmp_path, "downloaded_file_async.txt")
        file_content = b"Downloaded file content async"
        expected_name = blob_uri_response["Name"]

        # Mock the get attachment endpoint
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            method="GET",
            status_code=200,
            json=blob_uri_response,
        )

        # Mock the blob download
        httpx_mock.add_response(
            url=blob_uri_response["BlobFileAccess"]["Uri"],
            method="GET",
            status_code=200,
            content=file_content,
        )

        # Act
        result = await service.download_async(
            key=attachment_key,
            destination_path=destination_path,
        )

        # Assert
        assert result == expected_name
        assert os.path.exists(destination_path)
        with open(destination_path, "rb") as f:
            assert f.read() == file_content

    def test_delete(
        self,
        httpx_mock: HTTPXMock,
        service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Test deleting an attachment.

        Args:
            httpx_mock: HTTPXMock fixture for mocking HTTP requests.
            service: AttachmentsService fixture.
            base_url: Base URL fixture for the API endpoint.
            org: Organization fixture for the API path.
            tenant: Tenant fixture for the API path.
            version: Version fixture for the user agent header.
        """
        # Arrange
        attachment_key = uuid.UUID("12345678-1234-1234-1234-123456789012")

        # Mock the delete attachment endpoint
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            method="DELETE",
            status_code=204,
        )

        # Act
        service.delete(key=attachment_key)

        # Verify the request
        request = httpx_mock.get_request()
        if request is None:
            raise Exception("No request was sent")

        assert request.method == "DELETE"
        assert (
            request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})"
        )
        assert HEADER_USER_AGENT in request.headers
        assert request.headers[HEADER_USER_AGENT].startswith(
            f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AttachmentsService.delete/{version}"
        )

    @pytest.mark.asyncio
    async def test_delete_async(
        self,
        httpx_mock: HTTPXMock,
        service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Test asynchronously deleting an attachment.

        Args:
            httpx_mock: HTTPXMock fixture for mocking HTTP requests.
            service: AttachmentsService fixture.
            base_url: Base URL fixture for the API endpoint.
            org: Organization fixture for the API path.
            tenant: Tenant fixture for the API path.
            version: Version fixture for the user agent header.
        """
        # Arrange
        attachment_key = uuid.UUID("12345678-1234-1234-1234-123456789012")

        # Mock the delete attachment endpoint
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            method="DELETE",
            status_code=204,
        )

        # Act
        await service.delete_async(key=attachment_key)

        # Verify the request
        request = httpx_mock.get_request()
        if request is None:
            raise Exception("No request was sent")

        assert request.method == "DELETE"
        assert (
            request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})"
        )
        assert HEADER_USER_AGENT in request.headers
        assert request.headers[HEADER_USER_AGENT].startswith(
            f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.AttachmentsService.delete_async/{version}"
        )
