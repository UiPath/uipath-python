import json
import uuid

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.attachments_service import AttachmentsService
from uipath._services.processes_service import ProcessesService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models.job import Job


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> ProcessesService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    attachments_service = AttachmentsService(
        config=config, execution_context=execution_context
    )
    return ProcessesService(
        config=config,
        execution_context=execution_context,
        attachment_service=attachments_service,
    )


class TestProcessesService:
    def test_invoke(
        self,
        httpx_mock: HTTPXMock,
        service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        process_name = "test-process"
        input_arguments = {"key": "value"}
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            status_code=200,
            json={
                "value": [
                    {
                        "Key": "test-job-key",
                        "State": "Running",
                        "StartTime": "2024-01-01T00:00:00Z",
                        "Id": 123,
                    }
                ]
            },
        )

        job = service.invoke(process_name, input_arguments)

        assert isinstance(job, Job)
        assert job.key == "test-job-key"
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )
        assert sent_request.content.decode("utf-8") == json.dumps(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": json.dumps(input_arguments),
                }
            },
            separators=(",", ":"),
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ProcessesService.invoke/{version}"
        )

    def test_invoke_without_input_arguments(
        self,
        httpx_mock: HTTPXMock,
        service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        process_name = "test-process"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            status_code=200,
            json={
                "value": [
                    {
                        "Key": "test-job-key",
                        "State": "Running",
                        "StartTime": "2024-01-01T00:00:00Z",
                        "Id": 123,
                    }
                ]
            },
        )

        job = service.invoke(process_name)

        assert isinstance(job, Job)
        assert job.key == "test-job-key"
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )
        assert sent_request.content.decode("utf-8") == json.dumps(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": "{}",
                }
            },
            separators=(",", ":"),
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ProcessesService.invoke/{version}"
        )

    def test_invoke_over_10k_limit_input(
        self,
        httpx_mock: HTTPXMock,
        service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        process_name = "test-process"
        # Create input arguments that exceed 10k characters
        large_text = "a" * 10001
        input_arguments = {"large_text": large_text}

        test_attachment_id = uuid.uuid4()
        blob_uri = "https://test-storage.com/test-container/test-blob"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments",
            method="POST",
            status_code=201,
            json={
                "Id": str(test_attachment_id),
                "Name": "test-input.json",
                "BlobFileAccess": {
                    "Uri": blob_uri,
                    "Headers": {
                        "Keys": ["x-ms-blob-type", "Content-Type"],
                        "Values": ["BlockBlob", "application/json"],
                    },
                    "RequiresAuth": False,
                },
            },
        )

        httpx_mock.add_response(
            url=blob_uri,
            method="PUT",
            status_code=201,
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            status_code=200,
            json={
                "value": [
                    {
                        "Key": "test-job-key",
                        "State": "Running",
                        "StartTime": "2024-01-01T00:00:00Z",
                        "Id": 123,
                    }
                ]
            },
        )

        job = service.invoke(process_name, input_arguments)

        assert isinstance(job, Job)
        assert job.key == "test-job-key"
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        # attachment creation, blob upload, job start
        requests = httpx_mock.get_requests()
        assert len(requests) == 3

        attachment_request = requests[0]
        assert attachment_request.method == "POST"
        assert "Attachments" in str(attachment_request.url)

        blob_request = requests[1]
        assert blob_request.method == "PUT"
        assert blob_request.url == blob_uri

        job_request = requests[2]
        assert job_request.method == "POST"
        assert (
            job_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )

        # verify InputFile is used
        job_content = json.loads(job_request.content.decode("utf-8").replace("'", '"'))
        assert "startInfo" in job_content
        assert "ReleaseName" in job_content["startInfo"]
        assert job_content["startInfo"]["ReleaseName"] == process_name
        assert "InputFile" in job_content["startInfo"]
        assert "InputArguments" not in job_content["startInfo"]
        assert job_content["startInfo"]["InputFile"] == str(test_attachment_id)

        assert HEADER_USER_AGENT in job_request.headers
        assert (
            job_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ProcessesService.invoke/{version}"
        )

    @pytest.mark.asyncio
    async def test_invoke_async(
        self,
        httpx_mock: HTTPXMock,
        service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        process_name = "test-process"
        input_arguments = {"key": "value"}
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            status_code=200,
            json={
                "value": [
                    {
                        "Key": "test-job-key",
                        "State": "Running",
                        "StartTime": "2024-01-01T00:00:00Z",
                        "Id": 123,
                    }
                ]
            },
        )

        job = await service.invoke_async(process_name, input_arguments)

        assert isinstance(job, Job)
        assert job.key == "test-job-key"
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )
        assert sent_request.content.decode("utf-8") == json.dumps(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": json.dumps(input_arguments),
                }
            },
            separators=(",", ":"),
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ProcessesService.invoke_async/{version}"
        )

    @pytest.mark.asyncio
    async def test_invoke_async_without_input_arguments(
        self,
        httpx_mock: HTTPXMock,
        service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        process_name = "test-process"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            status_code=200,
            json={
                "value": [
                    {
                        "Key": "test-job-key",
                        "State": "Running",
                        "StartTime": "2024-01-01T00:00:00Z",
                        "Id": 123,
                    }
                ]
            },
        )

        job = await service.invoke_async(process_name)

        assert isinstance(job, Job)
        assert job.key == "test-job-key"
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "POST"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )
        assert sent_request.content.decode("utf-8") == json.dumps(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": "{}",
                }
            },
            separators=(",", ":"),
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ProcessesService.invoke_async/{version}"
        )

    @pytest.mark.asyncio
    async def test_invoke_async_over_10k_limit_input(
        self,
        httpx_mock: HTTPXMock,
        service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        process_name = "test-process"
        # Create input arguments that exceed 10k characters
        large_text = "a" * 10001
        input_arguments = {"large_text": large_text}

        test_attachment_id = uuid.uuid4()
        blob_uri = "https://test-storage.com/test-container/test-blob"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments",
            method="POST",
            status_code=201,
            json={
                "Id": str(test_attachment_id),
                "Name": "test-input.json",
                "BlobFileAccess": {
                    "Uri": blob_uri,
                    "Headers": {
                        "Keys": ["x-ms-blob-type", "Content-Type"],
                        "Values": ["BlockBlob", "application/json"],
                    },
                    "RequiresAuth": False,
                },
            },
        )

        httpx_mock.add_response(
            url=blob_uri,
            method="PUT",
            status_code=201,
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            status_code=200,
            json={
                "value": [
                    {
                        "Key": "test-job-key",
                        "State": "Running",
                        "StartTime": "2024-01-01T00:00:00Z",
                        "Id": 123,
                    }
                ]
            },
        )

        job = await service.invoke_async(process_name, input_arguments)

        assert isinstance(job, Job)
        assert job.key == "test-job-key"
        assert job.state == "Running"
        assert job.start_time == "2024-01-01T00:00:00Z"
        assert job.id == 123

        # attachment creation, blob upload, job start
        requests = httpx_mock.get_requests()
        assert len(requests) == 3

        attachment_request = requests[0]
        assert attachment_request.method == "POST"
        assert "Attachments" in str(attachment_request.url)

        blob_request = requests[1]
        assert blob_request.method == "PUT"
        assert blob_request.url == blob_uri

        job_request = requests[2]
        assert job_request.method == "POST"
        assert (
            job_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )

        # verify InputFile is used
        job_content = json.loads(job_request.content.decode("utf-8").replace("'", '"'))
        assert "startInfo" in job_content
        assert "ReleaseName" in job_content["startInfo"]
        assert job_content["startInfo"]["ReleaseName"] == process_name
        assert "InputFile" in job_content["startInfo"]
        assert "InputArguments" not in job_content["startInfo"]
        assert job_content["startInfo"]["InputFile"] == str(test_attachment_id)

        assert HEADER_USER_AGENT in job_request.headers
        assert (
            job_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ProcessesService.invoke_async/{version}"
        )
