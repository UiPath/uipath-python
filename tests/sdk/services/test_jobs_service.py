import json

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.jobs_service import JobsService
from uipath._utils.constants import HEADER_USER_AGENT
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
