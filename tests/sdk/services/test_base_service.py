from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from httpx import Headers
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services._base_service import BaseService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models.exceptions import EnrichedException


@pytest.fixture
def service(config: Config, execution_context: ExecutionContext) -> BaseService:
    return BaseService(config=config, execution_context=execution_context)


class TestBaseService:
    def test_init_base_service(self, service: BaseService):
        assert service is not None

    def test_base_service_default_headers(self, service: BaseService, secret: str):
        assert service.default_headers == {
            "Accept": "application/json",
            "Authorization": f"Bearer {secret}",
        }

    class TestRequest:
        def test_simple_request(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
            secret: str,
        ):
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "test"},
            )

            response = service.request("GET", endpoint)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{base_url}{org}{tenant}{endpoint}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequest.test_simple_request/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {secret}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}

    class TestRequestAsync:
        @pytest.mark.anyio
        async def test_simple_request_async(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
            secret: str,
        ):
            endpoint = "/endpoint"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "test"},
            )

            response = await service.request_async("GET", endpoint)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{base_url}{org}{tenant}{endpoint}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequestAsync.test_simple_request_async/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {secret}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}

    class TestRetryAfterParsing:
        """Tests for the _parse_retry_after method."""

        def test_parse_retry_after_with_seconds(self, service: BaseService):
            """Test parsing Retry-After header with seconds value."""
            headers = Headers({"Retry-After": "5"})
            result = service._parse_retry_after(headers)
            assert result == 5.0

        def test_parse_retry_after_with_date(self, service: BaseService):
            """Test parsing Retry-After header with HTTP date value."""
            future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
            retry_after_date = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
            headers = Headers({"Retry-After": retry_after_date})
            result = service._parse_retry_after(headers)
            assert 9.0 <= result <= 11.0

        def test_parse_retry_after_with_past_date(self, service: BaseService):
            """Test parsing Retry-After header with past date returns 0.0 (RFC 7231)."""
            past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
            retry_after_date = past_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
            headers = Headers({"Retry-After": retry_after_date})
            result = service._parse_retry_after(headers)
            assert result == 0.0  # Past dates allow immediate retry per RFC 7231

        def test_parse_retry_after_missing(self, service: BaseService):
            """Test parsing missing Retry-After header returns default 1.0."""
            headers = Headers({})
            result = service._parse_retry_after(headers)
            assert result == 1.0

        def test_parse_retry_after_invalid(self, service: BaseService):
            """Test parsing invalid Retry-After header returns default 1.0."""
            headers = Headers({"Retry-After": "invalid"})
            result = service._parse_retry_after(headers)
            assert result == 1.0

        def test_parse_retry_after_zero(self, service: BaseService):
            """Test parsing Retry-After: 0 returns 0.0 (RFC 7231 compliance)."""
            headers = Headers({"Retry-After": "0"})
            result = service._parse_retry_after(headers)
            assert result == 0.0

        def test_parse_retry_after_negative(self, service: BaseService):
            """Test parsing negative Retry-After returns 0.0 (prevents ValueError)."""
            headers = Headers({"Retry-After": "-5"})
            result = service._parse_retry_after(headers)
            assert result == 0.0  # Clamped to prevent time.sleep(negative) error

    class TestRequest429Retry:
        """Tests for 429 rate limit retry logic in request()."""

        def test_429_retry_with_numeric_retry_after(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that 429 with numeric Retry-After retries correctly."""
            endpoint = "/endpoint"

            # First request returns 429 with Retry-After: 1
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "1"},
            )
            # Second request succeeds
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.05),
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            assert response.json() == {"test": "success"}
            mock_sleep.assert_called_once()
            sleep_time = mock_sleep.call_args[0][0]
            assert 1.0 <= sleep_time <= 1.1

        def test_429_retry_with_date_retry_after(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that 429 with date Retry-After retries correctly."""
            endpoint = "/endpoint"
            future_time = datetime.now(timezone.utc) + timedelta(seconds=2)
            retry_after_date = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": retry_after_date},
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.05),
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            mock_sleep.assert_called_once()
            sleep_time = mock_sleep.call_args[0][0]
            assert 1.0 <= sleep_time <= 3.0

        def test_429_retry_without_retry_after(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that 429 without Retry-After uses default 1.0 second."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.05),
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            mock_sleep.assert_called_once()
            sleep_time = mock_sleep.call_args[0][0]
            assert 1.0 <= sleep_time <= 1.1

        def test_429_max_retries_exceeded(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that max retries are respected for 429 errors."""
            endpoint = "/endpoint"

            # Return 429 for all 4 attempts (initial + 3 retries)
            for _ in range(4):
                httpx_mock.add_response(
                    url=f"{base_url}{org}{tenant}{endpoint}",
                    status_code=429,
                    headers={"Retry-After": "1"},
                )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.05),
            ):
                with pytest.raises(EnrichedException):
                    service.request("GET", endpoint)

            # Should sleep 3 times (MAX_RETRIES)
            assert mock_sleep.call_count == 3

        def test_429_retry_includes_jitter(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that jitter is applied to retry delay."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "10"},
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.5) as mock_random,
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            mock_random.assert_called_once_with(0, 1.0)
            sleep_time = mock_sleep.call_args[0][0]
            assert sleep_time == 10.5

        def test_429_retry_logs_warning(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
            caplog,
        ):
            """Test that retry logs a warning message."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "2"},
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with patch("time.sleep"), patch("random.uniform", return_value=0.1):
                service.request("GET", endpoint)

            assert any(
                "Rate limited (429)" in record.message for record in caplog.records
            )
            assert any("attempt 1/3" in record.message for record in caplog.records)

        def test_429_first_attempt_success(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that successful first request doesn't trigger retry."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with patch("time.sleep") as mock_sleep:
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            mock_sleep.assert_not_called()

        def test_429_second_attempt_success(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that retry stops after successful response."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "1"},
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.05),
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            # Should only sleep once (first retry)
            assert mock_sleep.call_count == 1

        def test_429_multiple_consecutive_retries(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test handling of multiple consecutive 429 responses."""
            endpoint = "/endpoint"

            # Two consecutive 429s, then success
            for _ in range(2):
                httpx_mock.add_response(
                    url=f"{base_url}{org}{tenant}{endpoint}",
                    status_code=429,
                    headers={"Retry-After": "1"},
                )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.05),
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            assert response.json() == {"test": "success"}
            assert mock_sleep.call_count == 2  # Two retries

        def test_429_preserves_custom_headers(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that custom headers are preserved through 429 retries."""
            endpoint = "/endpoint"
            custom_value = "CustomValue"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "1"},
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with patch("time.sleep"), patch("random.uniform", return_value=0.05):
                response = service.request(
                    "GET", endpoint, headers={"X-Custom-Header": custom_value}
                )

            assert response.status_code == 200

            # Verify both requests had the custom header
            requests = httpx_mock.get_requests()
            assert len(requests) == 2
            for req in requests:
                assert req.headers["X-Custom-Header"] == custom_value
                assert HEADER_USER_AGENT in req.headers

        def test_429_retry_after_zero(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that Retry-After: 0 results in immediate retry (RFC 7231)."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "0"},
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.0),
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            mock_sleep.assert_called_once()
            sleep_time = mock_sleep.call_args[0][0]
            assert sleep_time == 0.0  # Should sleep for 0 seconds (immediate retry)

    class TestRequestAsync429Retry:
        """Tests for 429 rate limit retry logic in request_async()."""

        @pytest.mark.anyio
        async def test_429_retry_async(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that async 429 retry works with asyncio.sleep."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "1"},
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            mock_sleep = Mock()

            async def fake_sleep(seconds):
                mock_sleep(seconds)

            with (
                patch("asyncio.sleep", side_effect=fake_sleep),
                patch("random.uniform", return_value=0.05),
            ):
                response = await service.request_async("GET", endpoint)

            assert response.status_code == 200
            mock_sleep.assert_called_once()
            sleep_time = mock_sleep.call_args[0][0]
            assert 1.0 <= sleep_time <= 1.1

        @pytest.mark.anyio
        async def test_429_max_retries_exceeded_async(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that max retries are respected in async for 429 errors."""
            endpoint = "/endpoint"

            for _ in range(4):
                httpx_mock.add_response(
                    url=f"{base_url}{org}{tenant}{endpoint}",
                    status_code=429,
                    headers={"Retry-After": "1"},
                )

            mock_sleep = Mock()

            async def fake_sleep(seconds):
                mock_sleep(seconds)

            with (
                patch("asyncio.sleep", side_effect=fake_sleep),
                patch("random.uniform", return_value=0.05),
            ):
                with pytest.raises(EnrichedException):
                    await service.request_async("GET", endpoint)

            assert mock_sleep.call_count == 3

    class TestTenacityInteraction:
        """Tests for interaction between tenacity (5xx/timeout) and manual 429 retry."""

        def test_500_error_uses_tenacity_not_429_logic(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that 500 errors use tenacity retry, not 429 retry logic."""
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=500,
            )
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with patch("time.sleep") as mock_sleep:
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            # Tenacity should handle the retry, not our 429 logic
            # Tenacity uses exponential backoff, our 429 logic uses Retry-After
            mock_sleep.assert_called()

        def test_429_after_500_retry(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            """Test that 429 logic works after tenacity handles 500 error."""
            endpoint = "/endpoint"

            # First: 500 error (tenacity retries)
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=500,
            )
            # Second: 429 error (our manual retry)
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=429,
                headers={"Retry-After": "1"},
            )
            # Third: Success
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "success"},
            )

            with (
                patch("time.sleep") as mock_sleep,
                patch("random.uniform", return_value=0.05),
            ):
                response = service.request("GET", endpoint)

            assert response.status_code == 200
            # Should have multiple sleep calls (tenacity + our 429 logic)
            assert mock_sleep.call_count >= 2
