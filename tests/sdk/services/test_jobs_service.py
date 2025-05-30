import json
import os
import shutil
import uuid
from typing import TYPE_CHECKING, Any, Generator, Tuple

import pytest
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.jobs_service import JobsService
from uipath._utils.constants import HEADER_USER_AGENT, TEMP_ATTACHMENTS_FOLDER
from uipath.models.job import Job

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> JobsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    jobs_service = JobsService(config=config, execution_context=execution_context)
    # We'll leave the real AttachmentsService for HTTP tests,
    # and mock it in specific tests as needed
    return jobs_service


@pytest.fixture
def temp_attachments_dir(tmp_path: Any) -> Generator[str, None, None]:
    """Create a temporary directory for attachments and clean it up after the test.

    Args:
        tmp_path: Pytest's temporary directory fixture.

    Returns:
        The path to the temporary directory.
    """
    test_temp_dir = os.path.join(tmp_path, TEMP_ATTACHMENTS_FOLDER)
    os.makedirs(test_temp_dir, exist_ok=True)

    yield test_temp_dir

    # Clean up the directory after the test
    if os.path.exists(test_temp_dir):
        shutil.rmtree(test_temp_dir)


@pytest.fixture
def temp_file(tmp_path: Any) -> Generator[Tuple[str, str, str], None, None]:
    """Create a temporary file and clean it up after the test.

    Args:
        tmp_path: Pytest's temporary directory fixture.

    Returns:
        A tuple containing the file content, file name, and file path.
    """
    content = "Test source file content"
    name = f"test_file_{uuid.uuid4()}.txt"
    path = os.path.join(tmp_path, name)

    with open(path, "w") as f:
        f.write(content)

    yield content, name, path

    # Clean up the file after the test
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def local_attachment_file(
    temp_attachments_dir: str,
) -> Generator[Tuple[uuid.UUID, str, str], None, None]:
    """Creates a local attachment file in the temporary attachments directory.

    Args:
        temp_attachments_dir: The temporary attachments directory.

    Returns:
        A tuple containing the attachment ID, file name, and file content.
    """
    attachment_id = uuid.uuid4()
    file_name = "test_local_file.txt"
    file_content = "Local test content"

    # Create the local file with the format {uuid}_{filename}
    file_path = os.path.join(temp_attachments_dir, f"{attachment_id}_{file_name}")
    with open(file_path, "w") as f:
        f.write(file_content)

    yield attachment_id, file_name, file_content

    # Cleanup is handled by temp_attachments_dir fixture


class TestJobsService:
    def test_retrieve(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        job_key = "test-job-key"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=200,
            json={
                "Key": job_key,
                "State": "Running",
                "StartTime": "2024-01-01T00:00:00Z",
                "Id": 123,
            },
        )

        job = service.retrieve(job_key)

        assert isinstance(job, Job)
        assert job.key == job_key
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.JobsService.retrieve/{version}"
        )

    @pytest.mark.asyncio
    async def test_retrieve_async(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        job_key = "test-job-key"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=200,
            json={
                "Key": job_key,
                "State": "Running",
                "StartTime": "2024-01-01T00:00:00Z",
                "Id": 123,
            },
        )

        job = await service.retrieve_async(job_key)

        assert isinstance(job, Job)
        assert job.key == job_key
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.JobsService.retrieve_async/{version}"
        )

    def test_resume_with_inbox_id(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        inbox_id = "test-inbox-id"
        payload = {"key": "value"}
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}",
            status_code=200,
        )

        service.resume(inbox_id=inbox_id, payload=payload)

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}"
        )
        assert json.loads(sent_request.content) == {"payload": payload}

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.JobsService.resume/{version}"
        )

    def test_resume_with_job_id(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        job_id = "test-job-id"
        inbox_id = "test-inbox-id"
        payload = {"key": "value"}

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/JobTriggers?$filter=JobId eq {job_id}&$top=1&$select=ItemKey",
            status_code=200,
            json={"value": [{"ItemKey": inbox_id}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}",
            status_code=200,
        )

        service.resume(job_id=job_id, payload=payload)

        sent_requests = httpx_mock.get_requests()
        assert sent_requests is not None
        assert sent_requests[1].method == "POST"
        assert (
            sent_requests[1].url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}"
        )
        assert json.loads(sent_requests[1].content) == {"payload": payload}

        assert HEADER_USER_AGENT in sent_requests[1].headers
        assert (
            sent_requests[1].headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.JobsService.resume/{version}"
        )

    @pytest.mark.asyncio
    async def test_resume_async_with_inbox_id(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        inbox_id = "test-inbox-id"
        payload = {"key": "value"}
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}",
            status_code=200,
        )

        await service.resume_async(inbox_id=inbox_id, payload=payload)

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}"
        )
        assert json.loads(sent_request.content) == {"payload": payload}

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.JobsService.resume_async/{version}"
        )

    @pytest.mark.asyncio
    async def test_resume_async_with_job_id(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        job_id = "test-job-id"
        inbox_id = "test-inbox-id"
        payload = {"key": "value"}

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/JobTriggers?$filter=JobId eq {job_id}&$top=1&$select=ItemKey",
            status_code=200,
            json={"value": [{"ItemKey": inbox_id}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}",
            status_code=200,
        )

        await service.resume_async(job_id=job_id, payload=payload)

        sent_requests = httpx_mock.get_requests()
        assert sent_requests is not None
        assert sent_requests[1].method == "POST"
        assert (
            sent_requests[1].url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}"
        )
        assert json.loads(sent_requests[1].content) == {"payload": payload}

        assert HEADER_USER_AGENT in sent_requests[1].headers
        assert (
            sent_requests[1].headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.JobsService.resume_async/{version}"
        )

    def test_list_attachments(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        job_key = uuid.uuid4()

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/GetByJobKey?jobKey={job_key}",
            method="GET",
            status_code=200,
            json=[
                {
                    "attachmentId": "12345678-1234-1234-1234-123456789012",
                    "creationTime": "2023-01-01T12:00:00Z",
                    "lastModificationTime": "2023-01-02T12:00:00Z",
                },
                {
                    "attachmentId": "87654321-1234-1234-1234-123456789012",
                    "creationTime": "2023-01-03T12:00:00Z",
                    "lastModificationTime": "2023-01-04T12:00:00Z",
                },
            ],
        )

        attachments = service.list_attachments(job_key=job_key)

        assert len(attachments) == 2
        assert isinstance(attachments[0], str)
        assert attachments[0] == "12345678-1234-1234-1234-123456789012"
        assert isinstance(attachments[1], str)
        assert attachments[1] == "87654321-1234-1234-1234-123456789012"

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert (
            request.url.path
            == f"{org}{tenant}/orchestrator_/api/JobAttachments/GetByJobKey"
        )
        assert request.url.params.get("jobKey") == str(job_key)
        assert HEADER_USER_AGENT in request.headers

    @pytest.mark.asyncio
    async def test_list_attachments_async(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        job_key = uuid.uuid4()

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/GetByJobKey?jobKey={job_key}",
            method="GET",
            status_code=200,
            json=[
                {
                    "attachmentId": "12345678-1234-1234-1234-123456789012",
                    "creationTime": "2023-01-01T12:00:00Z",
                    "lastModificationTime": "2023-01-02T12:00:00Z",
                },
                {
                    "attachmentId": "87654321-1234-1234-1234-123456789012",
                    "creationTime": "2023-01-03T12:00:00Z",
                    "lastModificationTime": "2023-01-04T12:00:00Z",
                },
            ],
        )

        attachments = await service.list_attachments_async(job_key=job_key)

        assert len(attachments) == 2
        assert isinstance(attachments[0], str)
        assert attachments[0] == "12345678-1234-1234-1234-123456789012"
        assert isinstance(attachments[1], str)
        assert attachments[1] == "87654321-1234-1234-1234-123456789012"

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert (
            request.url.path
            == f"{org}{tenant}/orchestrator_/api/JobAttachments/GetByJobKey"
        )
        assert request.url.params.get("jobKey") == str(job_key)
        assert HEADER_USER_AGENT in request.headers

    def test_link_attachment(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        attachment_key = uuid.uuid4()
        job_key = uuid.uuid4()
        category = "Result"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post",
            method="POST",
            status_code=200,
        )

        service.link_attachment(
            attachment_key=attachment_key, job_key=job_key, category=category
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert (
            request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post"
        )
        assert HEADER_USER_AGENT in request.headers

        body = json.loads(request.content)
        assert body["attachmentId"] == str(attachment_key)
        assert body["jobKey"] == str(job_key)
        assert body["category"] == category

    @pytest.mark.asyncio
    async def test_link_attachment_async(
        self,
        httpx_mock: HTTPXMock,
        service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        attachment_key = uuid.uuid4()
        job_key = uuid.uuid4()
        category = "Result"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post",
            method="POST",
            status_code=200,
        )

        await service.link_attachment_async(
            attachment_key=attachment_key, job_key=job_key, category=category
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert (
            request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post"
        )
        assert HEADER_USER_AGENT in request.headers

        body = json.loads(request.content)
        assert body["attachmentId"] == str(attachment_key)
        assert body["jobKey"] == str(job_key)
        assert body["category"] == category

    def test_create_job_attachment_with_job(
        self,
        service: JobsService,
        mocker: MockerFixture,
    ) -> None:
        """Test creating a job attachment when a job is available.

        This tests that the attachment is created in UiPath and linked to the job
        when a job key is provided.

        Args:
            service: JobsService fixture.
            mocker: MockerFixture for mocking dependencies.
        """
        # Arrange
        job_key = str(uuid.uuid4())
        attachment_key = uuid.uuid4()
        content = "Test attachment content"
        name = "test_attachment.txt"

        # Mock the attachment service's upload method
        mock_upload = mocker.patch.object(
            service._attachments_service, "upload", return_value=attachment_key
        )

        # Mock the link_attachment method
        mock_link = mocker.patch.object(service, "link_attachment")

        # Act
        result = service.create_attachment(name=name, content=content, job_key=job_key)

        # Assert
        assert result == attachment_key
        mock_upload.assert_called_once_with(
            name=name,
            content=content,
            folder_key=None,
            folder_path=None,
        )
        mock_link.assert_called_once_with(
            attachment_key=attachment_key,
            job_key=uuid.UUID(job_key),
            category=None,
            folder_key=None,
            folder_path=None,
        )

    def test_create_job_attachment_with_job_context(
        self,
        config: Config,
        execution_context: ExecutionContext,
        monkeypatch: "MonkeyPatch",
        mocker: MockerFixture,
    ) -> None:
        """Test creating a job attachment when a job is available in the context.

        This tests that the attachment is created in UiPath and linked to the job
        when a job key is available in the execution context.

        Args:
            config: Config fixture.
            execution_context: ExecutionContext fixture.
            monkeypatch: MonkeyPatch fixture.
            mocker: MockerFixture for mocking dependencies.
        """
        # Arrange
        job_key = uuid.uuid4()
        attachment_key = uuid.uuid4()
        content = "Test attachment content"
        name = "test_attachment.txt"

        # Set job key in environment - must be string
        monkeypatch.setenv("UIPATH_JOB_KEY", str(job_key))
        monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")

        # Create fresh execution context after setting environment variables
        fresh_execution_context = ExecutionContext()
        service = JobsService(config=config, execution_context=fresh_execution_context)

        # Mock the attachment service's upload method
        mock_upload = mocker.patch.object(
            service._attachments_service, "upload", return_value=attachment_key
        )

        # Mock the link_attachment method
        mock_link = mocker.patch.object(service, "link_attachment")

        # Act
        result = service.create_attachment(name=name, content=content)

        # Assert
        assert result == attachment_key
        mock_upload.assert_called_once_with(
            name=name,
            content=content,
            folder_key=None,
            folder_path=None,
        )
        mock_link.assert_called_once_with(
            attachment_key=attachment_key,
            job_key=job_key,
            category=None,
            folder_key=None,
            folder_path=None,
        )

    def test_create_job_attachment_no_job(
        self,
        service: JobsService,
        temp_attachments_dir: str,
    ) -> None:
        """Test creating a job attachment when no job is available.

        This tests that the attachment is stored locally when no job key is provided
        or available in the context.

        Args:
            service: JobsService fixture.
            temp_attachments_dir: Temporary directory fixture that handles cleanup.
        """
        # Arrange
        content = "Test local attachment content"
        name = "test_local_attachment.txt"

        # Use the temporary directory provided by the fixture
        service._temp_dir = temp_attachments_dir

        # Act
        result = service.create_attachment(name=name, content=content)

        # Assert
        assert isinstance(result, uuid.UUID)
        # Verify file was created
        expected_path = os.path.join(temp_attachments_dir, f"{result}_{name}")
        assert os.path.exists(expected_path)

        # Check content
        with open(expected_path, "r") as f:
            assert f.read() == content

    def test_create_job_attachment_from_file(
        self,
        service: JobsService,
        temp_attachments_dir: str,
        temp_file: Tuple[str, str, str],
    ) -> None:
        """Test creating a job attachment from a file when no job is available.

        Args:
            service: JobsService fixture.
            temp_attachments_dir: Temporary directory fixture that handles cleanup.
            temp_file: Temporary file fixture that handles cleanup.
        """
        # Arrange
        source_content, source_name, source_path = temp_file

        # Use the temporary directory provided by the fixture
        service._temp_dir = temp_attachments_dir

        # Act
        result = service.create_attachment(name=source_name, source_path=source_path)

        # Assert
        assert isinstance(result, uuid.UUID)
        # Verify file was created
        expected_path = os.path.join(temp_attachments_dir, f"{result}_{source_name}")
        assert os.path.exists(expected_path)

        # Check content
        with open(expected_path, "r") as f:
            assert f.read() == source_content

    def test_create_job_attachment_validation_errors(
        self,
        service: JobsService,
    ) -> None:
        """Test validation errors in create_job_attachment.

        Args:
            service: JobsService fixture.
        """
        # Test missing both content and source_path
        with pytest.raises(ValueError, match="Content or source_path is required"):
            service.create_attachment(name="test.txt")

        # Test providing both content and source_path
        with pytest.raises(
            ValueError, match="Content and source_path are mutually exclusive"
        ):
            service.create_attachment(
                name="test.txt", content="test content", source_path="/path/to/file.txt"
            )

    @pytest.mark.asyncio
    async def test_create_job_attachment_async_with_job(
        self,
        service: JobsService,
        mocker: MockerFixture,
    ) -> None:
        """Test creating a job attachment asynchronously when a job is available.

        Args:
            service: JobsService fixture.
            mocker: MockerFixture for mocking dependencies.
        """
        # Arrange
        job_key = str(uuid.uuid4())
        attachment_key = uuid.uuid4()
        content = "Test attachment content"
        name = "test_attachment.txt"

        # Mock the attachment service's upload_async method
        # Create a mock that returns a coroutine returning a UUID
        async_mock = mocker.AsyncMock(return_value=attachment_key)
        mocker.patch.object(
            service._attachments_service, "upload_async", side_effect=async_mock
        )

        # Mock the link_attachment_async method
        mock_link = mocker.patch.object(
            service, "link_attachment_async", side_effect=mocker.AsyncMock()
        )

        # Act
        result = await service.create_attachment_async(
            name=name, content=content, job_key=job_key
        )

        # Assert
        assert result == attachment_key
        async_mock.assert_called_once_with(
            name=name,
            content=content,
            folder_key=None,
            folder_path=None,
        )
        mock_link.assert_called_once_with(
            attachment_key=attachment_key,
            job_key=uuid.UUID(job_key),
            category=None,
            folder_key=None,
            folder_path=None,
        )

    @pytest.mark.asyncio
    async def test_create_job_attachment_async_no_job(
        self,
        service: JobsService,
        temp_attachments_dir: str,
    ) -> None:
        """Test creating a job attachment asynchronously when no job is available.

        Args:
            service: JobsService fixture.
            temp_attachments_dir: Temporary directory fixture that handles cleanup.
        """
        # Arrange
        content = "Test local attachment content async"
        name = "test_local_attachment_async.txt"

        # Use the temporary directory provided by the fixture
        service._temp_dir = temp_attachments_dir

        # Act
        result = await service.create_attachment_async(name=name, content=content)

        # Assert
        assert isinstance(result, uuid.UUID)

        # Verify file was created
        expected_path = os.path.join(temp_attachments_dir, f"{result}_{name}")
        assert os.path.exists(expected_path)

        # Check content
        with open(expected_path, "r") as f:
            assert f.read() == content

    def test_create_job_attachment_with_job_from_file(
        self,
        service: JobsService,
        mocker: MockerFixture,
        temp_file: Tuple[str, str, str],
    ) -> None:
        """Test creating a job attachment from a file when a job is available.

        This tests that the attachment is created in UiPath from a file and linked to the job
        when a job key is provided.

        Args:
            service: JobsService fixture.
            mocker: MockerFixture for mocking dependencies.
            temp_file: Temporary file fixture that handles cleanup.
        """
        # Arrange
        job_key = str(uuid.uuid4())
        attachment_key = uuid.uuid4()

        # Get file details from fixture
        source_content, source_name, source_path = temp_file

        # Mock the attachment service's upload method
        mock_upload = mocker.patch.object(
            service._attachments_service, "upload", return_value=attachment_key
        )

        # Mock the link_attachment method
        mock_link = mocker.patch.object(service, "link_attachment")

        # Act
        result = service.create_attachment(
            name=source_name, source_path=source_path, job_key=job_key
        )

        # Assert
        assert result == attachment_key
        mock_upload.assert_called_once_with(
            name=source_name,
            source_path=source_path,
            folder_key=None,
            folder_path=None,
        )
        mock_link.assert_called_once_with(
            attachment_key=attachment_key,
            job_key=uuid.UUID(job_key),
            category=None,
            folder_key=None,
            folder_path=None,
        )

    @pytest.mark.asyncio
    async def test_create_job_attachment_async_with_job_from_file(
        self,
        service: JobsService,
        mocker: MockerFixture,
        temp_file: Tuple[str, str, str],
    ) -> None:
        """Test creating a job attachment asynchronously from a file when a job is available.

        Args:
            service: JobsService fixture.
            mocker: MockerFixture for mocking dependencies.
            temp_file: Temporary file fixture that handles cleanup.
        """
        # Arrange
        job_key = str(uuid.uuid4())
        attachment_key = uuid.uuid4()

        # Get file details from fixture
        source_content, source_name, source_path = temp_file

        # Mock the attachment service's upload_async method
        async_mock = mocker.AsyncMock(return_value=attachment_key)
        mocker.patch.object(
            service._attachments_service, "upload_async", side_effect=async_mock
        )

        # Mock the link_attachment_async method
        mock_link = mocker.patch.object(
            service, "link_attachment_async", side_effect=mocker.AsyncMock()
        )

        # Act
        result = await service.create_attachment_async(
            name=source_name, source_path=source_path, job_key=job_key
        )

        # Assert
        assert result == attachment_key
        async_mock.assert_called_once_with(
            name=source_name,
            source_path=source_path,
            folder_key=None,
            folder_path=None,
        )
        mock_link.assert_called_once_with(
            attachment_key=attachment_key,
            job_key=uuid.UUID(job_key),
            category=None,
            folder_key=None,
            folder_path=None,
        )

    @pytest.mark.asyncio
    async def test_create_job_attachment_async_from_file(
        self,
        service: JobsService,
        temp_attachments_dir: str,
        temp_file: Tuple[str, str, str],
    ) -> None:
        """Test creating a job attachment asynchronously from a file when no job is available.

        Args:
            service: JobsService fixture.
            temp_attachments_dir: Temporary directory fixture that handles cleanup.
            temp_file: Temporary file fixture that handles cleanup.
        """
        # Arrange
        # Get file details from fixture
        source_content, source_name, source_path = temp_file

        # Use the temporary directory provided by the fixture
        service._temp_dir = temp_attachments_dir

        # Act
        result = await service.create_attachment_async(
            name=source_name, source_path=source_path
        )

        # Assert
        assert isinstance(result, uuid.UUID)

        # Verify file was created
        expected_path = os.path.join(temp_attachments_dir, f"{result}_{source_name}")
        assert os.path.exists(expected_path)

        # Check content
        with open(expected_path, "r") as f:
            assert f.read() == source_content
