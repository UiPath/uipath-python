"""Tests for bulk job operations and N+1 fix."""

import pytest

# Test UUIDs
KEY1 = "11111111-1111-1111-1111-111111111111"
KEY2 = "22222222-2222-2222-2222-222222222222"
KEY3 = "33333333-3333-3333-3333-333333333333"


class TestResolveJobIdentifiers:
    """Test _resolve_job_identifiers() bulk query."""

    def test_resolve_single_key(self, jobs_service, httpx_mock, base_url, org, tenant):
        """Test resolving single job key to ID."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24filter=Key+in+%28%27{KEY1}%27%29&%24select=Id%2CKey&%24top=1",
            json={"value": [{"Key": KEY1, "Id": 100}]},
        )

        ids = jobs_service._resolve_job_identifiers(job_keys=[KEY1])

        assert ids == [100]
        assert len(httpx_mock.get_requests()) == 1

    def test_resolve_multiple_keys_single_query(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test resolving multiple job keys in single query (N+1 fix verification)."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24filter=Key+in+%28%27{KEY1}%27%2C%27{KEY2}%27%2C%27{KEY3}%27%29&%24select=Id%2CKey&%24top=3",
            json={
                "value": [
                    {"Key": KEY1, "Id": 100},
                    {"Key": KEY2, "Id": 101},
                    {"Key": KEY3, "Id": 102},
                ]
            },
        )

        ids = jobs_service._resolve_job_identifiers(job_keys=[KEY1, KEY2, KEY3])

        assert ids == [100, 101, 102]
        assert len(httpx_mock.get_requests()) == 1  # Only 1 API call!

    def test_resolve_preserves_order(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test that returned IDs maintain input key order."""
        # API may return in different order
        httpx_mock.add_response(
            json={
                "value": [
                    {"Key": KEY3, "Id": 102},
                    {"Key": KEY1, "Id": 100},
                    {"Key": KEY2, "Id": 101},
                ]
            },
        )

        ids = jobs_service._resolve_job_identifiers(job_keys=[KEY1, KEY2, KEY3])

        assert ids == [100, 101, 102]  # Correct order preserved

    def test_resolve_missing_key(self, jobs_service, httpx_mock, base_url, org, tenant):
        """Test error when some keys not found."""
        httpx_mock.add_response(
            json={
                "value": [
                    {"Key": KEY1, "Id": 100},
                    # KEY2 missing
                    {"Key": KEY3, "Id": 102},
                ]
            },
        )

        with pytest.raises(LookupError, match=f"Jobs not found for keys: {KEY2}"):
            jobs_service._resolve_job_identifiers(job_keys=[KEY1, KEY2, KEY3])

    def test_resolve_empty_list(self, jobs_service):
        """Test handling of empty key list."""
        ids = jobs_service._resolve_job_identifiers(job_keys=[])
        assert ids == []

    def test_resolve_duplicate_keys(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test that duplicate keys are handled correctly."""
        httpx_mock.add_response(
            json={
                "value": [
                    {"Key": KEY1, "Id": 100},
                    {"Key": KEY2, "Id": 101},
                ]
            },
        )

        # Request with duplicates
        ids = jobs_service._resolve_job_identifiers(job_keys=[KEY1, KEY2, KEY1])

        # Should return corresponding IDs maintaining order (including duplicates)
        assert ids == [100, 101, 100]
        assert len(httpx_mock.get_requests()) == 1  # Only 1 query despite duplicates

    def test_resolve_invalid_uuid(self, jobs_service):
        """Test that invalid UUID keys raise ValueError."""
        with pytest.raises(ValueError, match="Invalid job key format: not-a-uuid"):
            jobs_service._resolve_job_identifiers(job_keys=["not-a-uuid"])

    def test_resolve_large_batch_chunks(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test that large batches are chunked (50 keys per request)."""
        # Create 100 test keys (should result in 2 chunks)
        test_keys = [f"{i:08x}-0000-0000-0000-000000000000" for i in range(100)]

        # Mock first chunk (keys 0-49)
        chunk1_keys = test_keys[:50]
        chunk1_filter = "%27%2C%27".join(chunk1_keys)
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24filter=Key+in+%28%27{chunk1_filter}%27%29&%24select=Id%2CKey&%24top=50",
            json={"value": [{"Key": k, "Id": i} for i, k in enumerate(chunk1_keys)]},
        )

        # Mock second chunk (keys 50-99)
        chunk2_keys = test_keys[50:]
        chunk2_filter = "%27%2C%27".join(chunk2_keys)
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24filter=Key+in+%28%27{chunk2_filter}%27%29&%24select=Id%2CKey&%24top=50",
            json={
                "value": [{"Key": k, "Id": i + 50} for i, k in enumerate(chunk2_keys)]
            },
        )

        ids = jobs_service._resolve_job_identifiers(job_keys=test_keys)

        assert len(ids) == 100
        assert len(httpx_mock.get_requests()) == 2  # 2 chunks = 2 API calls


class TestStopWithBulkResolution:
    """Test stop() uses bulk resolution and pure spec pattern."""

    def test_stop_multiple_jobs_only_two_calls(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test stopping multiple jobs makes only 2 API calls (resolve + stop)."""
        # Mock bulk resolution
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs?%24filter=Key+in+%28%27{KEY1}%27%2C%27{KEY2}%27%29&%24select=Id%2CKey&%24top=2",
            json={"value": [{"Key": KEY1, "Id": 100}, {"Key": KEY2, "Id": 101}]},
        )

        # Mock stop request
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StopJobs",
            method="POST",
            json={},
        )

        jobs_service.stop(job_keys=[KEY1, KEY2], strategy="SoftStop")

        requests = httpx_mock.get_requests()
        assert len(requests) == 2  # Not N+1!

        # Verify stop request body matches Swagger schema
        import json

        stop_request = requests[-1]
        body = json.loads(stop_request.content)
        assert body == {"jobIds": [100, 101], "strategy": "SoftStop"}
        assert all(isinstance(id, int) for id in body["jobIds"])  # int64 validation

    def test_stop_single_job(self, jobs_service, httpx_mock, base_url, org, tenant):
        """Test stopping single job."""
        # Mock bulk resolution
        httpx_mock.add_response(
            json={"value": [{"Key": KEY1, "Id": 100}]},
        )

        # Mock stop request
        httpx_mock.add_response(
            method="POST",
            json={},
        )

        jobs_service.stop(job_keys=[KEY1], strategy="Kill")

        requests = httpx_mock.get_requests()
        assert len(requests) == 2

    def test_stop_invalid_uuid_raises_error(self, jobs_service):
        """Test that invalid UUID in stop() raises ValueError."""
        with pytest.raises(ValueError, match="Invalid job key format"):
            jobs_service.stop(job_keys=["invalid-uuid"])

    @pytest.mark.asyncio
    async def test_stop_async_uses_async_resolution(
        self, jobs_service, httpx_mock, base_url, org, tenant
    ):
        """Test stop_async uses async bulk resolution."""
        httpx_mock.add_response(
            json={"value": [{"Key": KEY1, "Id": 100}]},
        )

        httpx_mock.add_response(
            method="POST",
            json={},
        )

        await jobs_service.stop_async(job_keys=[KEY1])

        assert len(httpx_mock.get_requests()) == 2
