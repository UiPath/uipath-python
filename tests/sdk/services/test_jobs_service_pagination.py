"""Tests for JobsService PagedResult pagination."""

import pytest

from uipath.platform.common.paging import PagedResult
from uipath.platform.orchestrator.job import Job


class TestJobsListPagination:
    """Test list() pagination with PagedResult."""

    def test_list_returns_paged_result(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test that list() returns PagedResult[Job]."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=0&%24top=100",
            json={"value": [{"Key": "job-1", "Id": 1, "State": "Successful"}]},
        )

        result = jobs_service.list()

        assert isinstance(result, PagedResult)
        assert len(result.items) == 1
        assert isinstance(result.items[0], Job)
        assert result.skip == 0
        assert result.top == 100

    def test_list_has_more_true_when_full_page(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test has_more=True when page is full."""
        jobs = [{"Key": f"job-{i}", "Id": i, "State": "Successful"} for i in range(100)]
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=0&%24top=100",
            json={"value": jobs},
        )

        result = jobs_service.list(top=100)

        assert result.has_more is True
        assert len(result.items) == 100

    def test_list_has_more_false_when_partial_page(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test has_more=False when page is partial."""
        jobs = [{"Key": f"job-{i}", "Id": i, "State": "Successful"} for i in range(50)]
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=0&%24top=100",
            json={"value": jobs},
        )

        result = jobs_service.list(top=100)

        assert result.has_more is False
        assert len(result.items) == 50

    def test_list_with_filter(self, jobs_service, httpx_mock, base_url, org, tenant):
        """Test list with OData filter."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24filter=State+eq+%27Successful%27&%24skip=0&%24top=100",
            json={"value": [{"Key": "job-1", "Id": 1, "State": "Successful"}]},
        )

        result = jobs_service.list(filter="State eq 'Successful'")

        assert len(result.items) == 1
        assert result.items[0].state == "Successful"

    def test_list_manual_pagination(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test manual pagination across multiple pages."""
        # First page
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=0&%24top=10",
            json={"value": [{"Key": f"job-{i}", "Id": i} for i in range(10)]},
        )
        # Second page
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=10&%24top=10",
            json={"value": [{"Key": f"job-{i}", "Id": i} for i in range(10, 15)]},
        )

        # Fetch first page
        page1 = jobs_service.list(skip=0, top=10)
        assert len(page1.items) == 10
        assert page1.has_more is True

        # Fetch second page
        page2 = jobs_service.list(skip=10, top=10)
        assert len(page2.items) == 5
        assert page2.has_more is False


class TestJobsListValidation:
    """Test parameter validation for list()."""

    def test_list_skip_exceeds_maximum(self, jobs_service):
        """Test error when skip > MAX_SKIP_OFFSET."""
        with pytest.raises(
            ValueError, match=r"skip must be <= 10000.*requested: 10001"
        ):
            jobs_service.list(skip=10001)

    def test_list_top_exceeds_maximum(self, jobs_service):
        """Test error when top > MAX_PAGE_SIZE."""
        with pytest.raises(ValueError, match=r"top must be <= 1000.*requested: 1001"):
            jobs_service.list(top=1001)

    def test_list_uses_shared_validation(self, jobs_service):
        """Test that list() uses shared validation utility."""
        with pytest.raises(ValueError, match="skip must be >= 0"):
            jobs_service.list(skip=-1)

        with pytest.raises(ValueError, match="top must be >= 1"):
            jobs_service.list(top=0)

    def test_list_skip_at_boundary(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test that skip=10000 is allowed."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=10000&%24top=100",
            json={"value": []},
        )

        result = jobs_service.list(skip=10000)
        assert result is not None

    def test_list_top_at_boundary(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test that top=1000 is allowed."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=0&%24top=1000",
            json={"value": []},
        )

        result = jobs_service.list(top=1000)
        assert result is not None


class TestJobsListAsync:
    """Test async version of list()."""

    @pytest.mark.asyncio
    async def test_list_async_returns_paged_result(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test that list_async() returns PagedResult[Job]."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24skip=0&%24top=100",
            json={"value": [{"Key": "job-1", "Id": 1}]},
        )

        result = await jobs_service.list_async()

        assert isinstance(result, PagedResult)
        assert len(result.items) == 1
