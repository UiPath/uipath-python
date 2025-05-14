import json

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
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
    return ProcessesService(config=config, execution_context=execution_context)


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
        assert sent_request.content.decode("utf-8") == str(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": json.dumps(input_arguments),
                }
            }
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
        assert sent_request.content.decode("utf-8") == str(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": "{}",
                }
            }
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
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
        assert sent_request.content.decode("utf-8") == str(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": json.dumps(input_arguments),
                }
            }
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
        assert sent_request.content.decode("utf-8") == str(
            {
                "startInfo": {
                    "ReleaseName": process_name,
                    "InputArguments": "{}",
                }
            }
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ProcessesService.invoke_async/{version}"
        )
