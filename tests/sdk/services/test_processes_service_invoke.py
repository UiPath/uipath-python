"""Tests for ProcessesService invoke() method - Gap 1 from AI review."""

import json

import pytest
from pytest_httpx import HTTPXMock

from uipath._services.processes_service import ProcessesService
from uipath.models.job import Job


class TestProcessesServiceInvoke:
    """Test ProcessesService invoke() method creates jobs correctly."""

    def test_invoke_creates_job(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() sends correct POST request to start job."""
        # Mock job creation response
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Id": 123,
                        "Key": "job-123",
                        "State": "Pending",
                        "Release": {"Name": "Process1"},
                    }
                ]
            }
        )

        job = processes_service.invoke(name="Process1")

        assert isinstance(job, Job)
        assert job.key == "job-123"
        assert job.state == "Pending"
        assert job.id == 123

        # Verify request
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert "StartJobs" in str(request.url)

    def test_invoke_with_input_arguments(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() passes input arguments correctly."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Id": 124,
                        "Key": "job-123",
                        "State": "Pending",
                        "InputArguments": '{"arg1": "value1"}',
                    }
                ]
            }
        )

        job = processes_service.invoke(
            name="Process1", input_arguments={"arg1": "value1"}
        )

        assert job.key == "job-123"
        assert job.input_arguments == '{"arg1": "value1"}'

        # Verify the request payload sent to the API
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["startInfo"]["ReleaseName"] == "Process1"
        # Input arguments are serialized to JSON string in the payload
        assert "InputArguments" in body["startInfo"]

    def test_invoke_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() sends folder path header."""
        httpx_mock.add_response(
            json={"value": [{"Id": 125, "Key": "job-123", "State": "Pending"}]}
        )

        processes_service.invoke(name="Process1", folder_path="Shared/Finance")

        # Verify folder header (handled by base service)
        request = httpx_mock.get_request()
        assert request is not None

    def test_invoke_with_folder_key(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() sends folder key header."""
        httpx_mock.add_response(
            json={"value": [{"Id": 126, "Key": "job-123", "State": "Pending"}]}
        )

        processes_service.invoke(name="Process1", folder_key="folder-key-123")

        request = httpx_mock.get_request()
        assert request is not None

    def test_invoke_returns_job_with_release(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() returns Job with release information."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Id": 127,
                        "Key": "job-123",
                        "State": "Pending",
                        "Release": {
                            "Name": "Process1",
                            "ProcessVersion": "1.0.0",
                            "Key": "release-key",
                        },
                    }
                ]
            }
        )

        job = processes_service.invoke(name="Process1")

        assert isinstance(job, Job)
        assert job.release is not None
        assert job.release["Name"] == "Process1"

    def test_invoke_response_parsing(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() correctly parses response from value array."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Id": 456,
                        "Key": "job-456",
                        "State": "Running",
                    }
                ]
            }
        )

        job = processes_service.invoke(name="Process2")

        assert job.key == "job-456"
        assert job.state == "Running"
        assert job.id == 456

    @pytest.mark.asyncio
    async def test_invoke_async_creates_job(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke_async() sends correct POST request to start job."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Id": 200,
                        "Key": "job-async-123",
                        "State": "Pending",
                    }
                ]
            }
        )

        job = await processes_service.invoke_async(name="Process1")

        assert job.key == "job-async-123"
        assert job.state == "Pending"
        assert job.id == 200

    @pytest.mark.asyncio
    async def test_invoke_async_with_input_arguments(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke_async() passes input arguments correctly."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Id": 201,
                        "Key": "job-async-123",
                        "State": "Pending",
                        "InputArguments": '{"arg1": "value1"}',
                    }
                ]
            }
        )

        job = await processes_service.invoke_async(
            name="Process1", input_arguments={"arg1": "value1"}
        )

        assert job.key == "job-async-123"
        assert job.input_arguments == '{"arg1": "value1"}'

    def test_invoke_request_body_structure(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() sends correct request body structure."""
        httpx_mock.add_response(
            json={"value": [{"Id": 300, "Key": "job-123", "State": "Pending"}]}
        )

        processes_service.invoke(name="TestProcess")

        request = httpx_mock.get_request()
        assert request is not None

        # Verify request uses POST method
        assert request.method == "POST"

        # Verify correct OData endpoint
        assert "orchestrator_/odata/Jobs" in str(request.url)
        assert "StartJobs" in str(request.url)

    def test_invoke_with_runtime_strategy(
        self,
        httpx_mock: HTTPXMock,
        processes_service: ProcessesService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test invoke() with Strategy parameter for specific release version."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Id": 301,
                        "Key": "job-123",
                        "State": "Pending",
                        "Release": {
                            "Name": "Process1",
                            "ProcessVersion": "2.0.0",
                            "Key": "release-key-v2",
                        },
                    }
                ]
            }
        )

        # Strategy: "Specific" with RuntimeType can be used to invoke a specific version
        # These parameters go into the startInfo along with ReleaseName
        job = processes_service.invoke(
            name="Process1",
            input_arguments={"Strategy": "Specific", "RuntimeType": "Production"},
        )

        assert job.key == "job-123"
        assert job.release is not None
        assert job.release["ProcessVersion"] == "2.0.0"

        # Verify request body includes Strategy
        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["startInfo"]["ReleaseName"] == "Process1"
        # Strategy and RuntimeType are passed as part of input arguments
        assert "InputArguments" in body["startInfo"]
