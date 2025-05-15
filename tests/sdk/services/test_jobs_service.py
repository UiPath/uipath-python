import json
import uuid

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.jobs_service import JobsService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models import Attachment
from uipath.models.job import Job


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> JobsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return JobsService(config=config, execution_context=execution_context)


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
        if sent_request is None:
            raise Exception("No request was sent")

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
        if sent_request is None:
            raise Exception("No request was sent")

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
        if sent_request is None:
            raise Exception("No request was sent")

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
        if sent_requests is None:
            raise Exception("No request was sent")

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
        if sent_request is None:
            raise Exception("No request was sent")

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
        if sent_requests is None:
            raise Exception("No request was sent")

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
        version: str,
    ) -> None:
        # Arrange
        job_key = uuid.uuid4()

        # Mock with query parameters
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/GetByJobKey?jobKey={job_key}",
            method="GET",
            status_code=200,
            json=[
                {
                    "Name": "document1.pdf",
                    "Key": "12345678-1234-1234-1234-123456789012",
                    "CreationTime": "2023-01-01T12:00:00Z",
                    "LastModificationTime": "2023-01-02T12:00:00Z",
                },
                {
                    "Name": "document2.pdf",
                    "Key": "87654321-1234-1234-1234-123456789012",
                    "CreationTime": "2023-01-03T12:00:00Z",
                    "LastModificationTime": "2023-01-04T12:00:00Z",
                },
            ],
        )

        # Act
        attachments = service.list_attachments(job_key=job_key)

        # Assert
        assert len(attachments) == 2
        assert isinstance(attachments[0], Attachment)
        assert attachments[0].name == "document1.pdf"
        assert attachments[0].key == uuid.UUID("12345678-1234-1234-1234-123456789012")
        assert isinstance(attachments[1], Attachment)
        assert attachments[1].name == "document2.pdf"
        assert attachments[1].key == uuid.UUID("87654321-1234-1234-1234-123456789012")

        # Verify the request
        request = httpx_mock.get_request()
        if request is None:
            raise Exception("No request was sent")

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
        # Arrange
        job_key = uuid.uuid4()

        # Mock with query parameters
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/GetByJobKey?jobKey={job_key}",
            method="GET",
            status_code=200,
            json=[
                {
                    "Name": "document1.pdf",
                    "Key": "12345678-1234-1234-1234-123456789012",
                    "CreationTime": "2023-01-01T12:00:00Z",
                    "LastModificationTime": "2023-01-02T12:00:00Z",
                },
                {
                    "Name": "document2.pdf",
                    "Key": "87654321-1234-1234-1234-123456789012",
                    "CreationTime": "2023-01-03T12:00:00Z",
                    "LastModificationTime": "2023-01-04T12:00:00Z",
                },
            ],
        )

        # Act
        attachments = await service.list_attachments_async(job_key=job_key)

        # Assert
        assert len(attachments) == 2
        assert isinstance(attachments[0], Attachment)
        assert attachments[0].name == "document1.pdf"
        assert attachments[0].key == uuid.UUID("12345678-1234-1234-1234-123456789012")
        assert isinstance(attachments[1], Attachment)
        assert attachments[1].name == "document2.pdf"
        assert attachments[1].key == uuid.UUID("87654321-1234-1234-1234-123456789012")

        # Verify the request
        request = httpx_mock.get_request()
        if request is None:
            raise Exception("No request was sent")
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
        # Arrange
        attachment_key = uuid.uuid4()
        job_key = uuid.uuid4()
        category = "Result"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post",
            method="POST",
            status_code=200,
        )

        # Act
        service.link_attachment(
            attachment_key=attachment_key, job_key=job_key, category=category
        )

        # Verify the request
        request = httpx_mock.get_request()
        if request is None:
            raise Exception("No request was sent")
        assert request.method == "POST"
        assert (
            request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post"
        )
        assert HEADER_USER_AGENT in request.headers

        # Verify request JSON body
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
        # Arrange
        attachment_key = uuid.uuid4()
        job_key = uuid.uuid4()
        category = "Result"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post",
            method="POST",
            status_code=200,
        )

        # Act
        await service.link_attachment_async(
            attachment_key=attachment_key, job_key=job_key, category=category
        )

        # Verify the request
        request = httpx_mock.get_request()
        if request is None:
            raise Exception("No request was sent")

        assert request.method == "POST"
        assert (
            request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/JobAttachments/Post"
        )
        assert HEADER_USER_AGENT in request.headers

        # Verify request JSON body
        body = json.loads(request.content)
        assert body["attachmentId"] == str(attachment_key)
        assert body["jobKey"] == str(job_key)
        assert body["category"] == category
