"""Comprehensive tests for JobsService operations.

Tests the ACTUAL implemented API signatures for job operations:
- list() with OData filtering and pagination (no expand/select)
- retrieve() by job_key or job_id (keyword-only arguments)
- exists() boolean checks by job_key
- stop() one or more jobs by job_keys list or job_ids list (with strategy parameter)
- Async variants for all operations
"""

from typing import Any, Dict

import pytest
from pytest_httpx import HTTPXMock

from uipath._services.jobs_service import JobsService
from uipath.models.job import Job


@pytest.fixture
def job_data() -> Dict[str, Any]:
    """Sample job response data."""
    return {
        "Key": "job-123-abc",
        "Id": 12345,
        "State": "Successful",
        "Info": "Job completed successfully",
        "CreationTime": "2024-01-15T10:30:00Z",
        "StartingTime": "2024-01-15T10:30:05Z",
        "EndTime": "2024-01-15T10:35:00Z",
        "ReleaseName": "MyProcess",
        "Type": "Unattended",
        "InputArguments": '{"arg1": "value1"}',
        "OutputArguments": '{"result": "success"}',
    }


@pytest.fixture
def jobs_list_data(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sample jobs list response."""
    return {
        "@odata.context": "https://test.uipath.com/odata/$metadata#Jobs",
        "@odata.count": 2,
        "value": [
            job_data,
            {
                "Key": "job-456-def",
                "Id": 67890,
                "State": "Running",
                "Info": "Job in progress",
                "CreationTime": "2024-01-15T11:00:00Z",
                "StartingTime": "2024-01-15T11:00:05Z",
                "ReleaseName": "AnotherProcess",
                "Type": "Unattended",
            },
        ],
    }


class TestJobsServiceList:
    """Tests for JobsService.list() method."""

    def test_list_jobs_basic(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        jobs_list_data: Dict[str, Any],
    ) -> None:
        """Test basic job listing."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24top=100&%24skip=0",
            json=jobs_list_data,
        )

        jobs = list(jobs_service.list())

        assert len(jobs) == 2
        assert all(isinstance(j, Job) for j in jobs)
        assert jobs[0].key == "job-123-abc"
        assert jobs[1].key == "job-456-def"

    def test_list_jobs_with_filter(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test listing jobs with OData filter."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24filter=State+eq+%27Successful%27&%24top=100&%24skip=0",
            json={"value": [job_data]},
        )

        jobs = list(jobs_service.list(filter="State eq 'Successful'"))

        assert len(jobs) == 1
        assert jobs[0].state == "Successful"

    def test_list_jobs_with_orderby(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        jobs_list_data: Dict[str, Any],
    ) -> None:
        """Test listing jobs with ordering."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24orderby=CreationTime+desc&%24top=100&%24skip=0",
            json=jobs_list_data,
        )

        jobs = list(jobs_service.list(orderby="CreationTime desc"))

        assert len(jobs) == 2

    def test_list_jobs_with_pagination(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test listing jobs with pagination parameters."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24top=10&%24skip=5",
            json={"value": [job_data]},
        )

        jobs = list(jobs_service.list(top=10, skip=5))

        assert len(jobs) == 1

    def test_list_jobs_auto_pagination(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test automatic pagination when more results available."""
        # First page
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24top=1&%24skip=0",
            json={"value": [job_data]},
        )
        # Second page (empty)
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24top=1&%24skip=1",
            json={"value": []},
        )

        jobs = list(jobs_service.list(top=1))

        assert len(jobs) == 1

    def test_list_jobs_with_folder_path(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        jobs_list_data: Dict[str, Any],
    ) -> None:
        """Test listing jobs with folder_path parameter."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24top=100&%24skip=0",
            json=jobs_list_data,
        )

        jobs = list(jobs_service.list(folder_path="Shared"))

        assert len(jobs) == 2

    def test_list_jobs_with_combined_filters(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test listing jobs with multiple filter parameters."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24filter=State+eq+%27Successful%27+and+ReleaseName+eq+%27MyProcess%27&%24orderby=CreationTime+desc&%24top=50&%24skip=0",
            json={"value": [job_data]},
        )

        jobs = list(
            jobs_service.list(
                filter="State eq 'Successful' and ReleaseName eq 'MyProcess'",
                orderby="CreationTime desc",
                top=50,
            )
        )

        assert len(jobs) == 1


class TestJobsServiceRetrieve:
    """Tests for JobsService.retrieve() method."""

    def test_retrieve_job_by_key(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test retrieving a job by its key."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json=job_data,
        )

        job = jobs_service.retrieve(job_key="job-123-abc")

        assert isinstance(job, Job)
        assert job.key == "job-123-abc"
        assert job.state == "Successful"

    def test_retrieve_job_not_found(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test retrieving non-existent job raises LookupError."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=invalid-key)",
            status_code=404,
        )

        with pytest.raises(LookupError, match="Job with key 'invalid-key' not found"):
            jobs_service.retrieve(job_key="invalid-key")

    def test_retrieve_job_with_folder_path(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test retrieving a job with folder context."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json=job_data,
        )

        job = jobs_service.retrieve(job_key="job-123-abc", folder_path="Shared")

        assert job.key == "job-123-abc"


class TestJobsServiceExists:
    """Tests for JobsService.exists() method."""

    def test_exists_job_true(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test exists check returns True when job exists."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json=job_data,
        )

        exists = jobs_service.exists(job_key="job-123-abc")

        assert exists is True

    def test_exists_job_false(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test exists check returns False when job doesn't exist."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=invalid-key)",
            status_code=404,
        )

        exists = jobs_service.exists(job_key="invalid-key")

        assert exists is False


class TestJobsServiceStop:
    """Tests for JobsService.stop() method."""

    def test_stop_single_job(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test stopping a single job by key."""
        # Mock retrieve endpoint (stop() calls retrieve() to get job ID)
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json={"Key": "job-123-abc", "Id": 12345, "State": "Running"},
        )

        httpx_mock.add_response(
            method="POST",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StopJobs",
            status_code=204,
        )

        jobs_service.stop(job_keys=["job-123-abc"])

        requests = httpx_mock.get_requests()
        assert len(requests) == 2  # retrieve + stop
        assert requests[0].method == "GET"  # retrieve
        assert requests[1].method == "POST"  # stop

    def test_stop_job_with_folder_path(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test stopping a job with folder context."""
        # Mock retrieve endpoint (stop() calls retrieve() to get job ID)
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json={"Key": "job-123-abc", "Id": 12345, "State": "Running"},
        )

        httpx_mock.add_response(
            method="POST",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StopJobs",
            status_code=204,
        )

        jobs_service.stop(job_keys=["job-123-abc"], folder_path="Shared")

        requests = httpx_mock.get_requests()
        assert len(requests) == 2  # retrieve + stop


class TestJobsServiceAsync:
    """Tests for async variants of job operations."""

    @pytest.mark.asyncio
    async def test_list_jobs_async(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        jobs_list_data: Dict[str, Any],
    ) -> None:
        """Test async job listing."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24top=100&%24skip=0",
            json=jobs_list_data,
        )

        jobs = []
        async for job in jobs_service.list_async():
            jobs.append(job)

        assert len(jobs) == 2
        assert all(isinstance(j, Job) for j in jobs)

    @pytest.mark.asyncio
    async def test_retrieve_job_async(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test async job retrieval."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json=job_data,
        )

        job = await jobs_service.retrieve_async(job_key="job-123-abc")

        assert isinstance(job, Job)
        assert job.key == "job-123-abc"

    @pytest.mark.asyncio
    async def test_exists_job_async(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
        job_data: Dict[str, Any],
    ) -> None:
        """Test async job existence check."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json=job_data,
        )

        exists = await jobs_service.exists_async(job_key="job-123-abc")

        assert exists is True

    @pytest.mark.asyncio
    async def test_stop_job_async(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test async job stop."""
        # Mock retrieve endpoint (stop_async() calls retrieve_async() to get job ID)
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier=job-123-abc)",
            json={"Key": "job-123-abc", "Id": 12345, "State": "Running"},
        )

        httpx_mock.add_response(
            method="POST",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StopJobs",
            status_code=204,
        )

        await jobs_service.stop_async(job_keys=["job-123-abc"])

        requests = httpx_mock.get_requests()
        assert len(requests) == 2  # retrieve + stop


class TestJobsServiceFieldMapping:
    """Tests for job field mapping and type conversions."""

    def test_job_state_mapping(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that job states are correctly mapped."""
        for state in ["Pending", "Running", "Successful", "Faulted", "Stopped"]:
            httpx_mock.add_response(
                method="GET",
                url=f"https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24filter=State+eq+%27{state}%27&%24top=100&%24skip=0",
                json={"value": [{"Key": f"job-{state}", "Id": 1, "State": state}]},
            )

            jobs = list(jobs_service.list(filter=f"State eq '{state}'"))
            assert jobs[0].state == state

    def test_job_type_mapping(
        self,
        jobs_service: JobsService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that job types are correctly mapped."""
        for job_type in ["Unattended", "Attended", "Development"]:
            httpx_mock.add_response(
                method="GET",
                url=f"https://test.uipath.com/org/tenant/orchestrator_/odata/Jobs?%24filter=Type+eq+%27{job_type}%27&%24top=100&%24skip=0",
                json={"value": [{"Key": f"job-{job_type}", "Id": 1, "Type": job_type}]},
            )

            jobs = list(jobs_service.list(filter=f"Type eq '{job_type}'"))
            assert jobs[0].model_extra.get("Type") == job_type
