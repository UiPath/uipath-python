import httpx
from tenacity import Future, RetryCallState, Retrying

from uipath.platform.common.retry import (
    _MAX_BACKOFF_DELAY,
    _MAX_RETRY_AFTER_DELAY,
    exponential_backoff_with_jitter,
    extract_retry_after_from_chain,
    is_retryable_platform_exception,
    is_retryable_response,
    parse_retry_after,
    platform_wait_strategy,
)
from uipath.platform.errors import EnrichedException


class TestParseRetryAfter:
    def test_valid_integer(self):
        assert parse_retry_after("120") == 120.0

    def test_valid_float(self):
        assert parse_retry_after("1.5") == 1.5

    def test_zero(self):
        assert parse_retry_after("0") == 0.0

    def test_whitespace(self):
        assert parse_retry_after("  30  ") == 30.0

    def test_negative_returns_none(self):
        assert parse_retry_after("-1") is None

    def test_non_numeric_returns_none(self):
        assert parse_retry_after("not-a-number") is None

    def test_http_date_returns_none(self):
        assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") is None

    def test_empty_string_returns_none(self):
        assert parse_retry_after("") is None


class TestExponentialBackoffWithJitter:
    def test_first_attempt(self):
        result = exponential_backoff_with_jitter(attempt=1, initial=1.0)
        # 1.0 * 2^0 + jitter(0,1) = 1.0 + [0, 1)
        assert 1.0 <= result < 2.0

    def test_second_attempt(self):
        result = exponential_backoff_with_jitter(attempt=2, initial=1.0)
        # 1.0 * 2^1 + jitter(0,1) = 2.0 + [0, 1)
        assert 2.0 <= result < 3.0

    def test_third_attempt(self):
        result = exponential_backoff_with_jitter(attempt=3, initial=1.0)
        # 1.0 * 2^2 + jitter(0,1) = 4.0 + [0, 1)
        assert 4.0 <= result < 5.0

    def test_growth_pattern(self):
        # With large enough initial, growth dominates jitter
        results = [
            exponential_backoff_with_jitter(attempt=i, initial=10.0)
            for i in range(1, 5)
        ]
        # Each base should roughly double (jitter is <=1.0, base starts at 10)
        for i in range(1, len(results)):
            assert results[i] > results[i - 1]

    def test_custom_initial(self):
        result = exponential_backoff_with_jitter(attempt=1, initial=5.0)
        assert 5.0 <= result < 6.0


class TestExtractRetryAfterFromChain:
    @staticmethod
    def _make_http_status_error(
        status_code: int, retry_after: str | None = None
    ) -> httpx.HTTPStatusError:
        headers = {}
        if retry_after is not None:
            headers["retry-after"] = retry_after
        response = httpx.Response(
            status_code=status_code,
            headers=headers,
            request=httpx.Request("GET", "https://example.com"),
        )
        return httpx.HTTPStatusError(
            message=f"{status_code}", request=response.request, response=response
        )

    def test_direct_http_status_error(self):
        err = self._make_http_status_error(429, retry_after="30")
        assert extract_retry_after_from_chain(err) == 30.0

    def test_enriched_exception_wrapping(self):
        http_err = self._make_http_status_error(429, retry_after="60")
        enriched = EnrichedException(http_err)
        enriched.__cause__ = http_err
        assert extract_retry_after_from_chain(enriched) == 60.0

    def test_missing_header(self):
        err = self._make_http_status_error(500)
        assert extract_retry_after_from_chain(err) is None

    def test_unrelated_exception(self):
        err = ValueError("something unrelated")
        assert extract_retry_after_from_chain(err) is None

    def test_zero_retry_after(self):
        err = self._make_http_status_error(429, retry_after="0")
        assert extract_retry_after_from_chain(err) == 0.0

    def test_negative_retry_after_ignored(self):
        err = self._make_http_status_error(429, retry_after="-5")
        assert extract_retry_after_from_chain(err) is None


def _make_http_status_error(
    status_code: int, retry_after: str | None = None
) -> httpx.HTTPStatusError:
    headers = {}
    if retry_after is not None:
        headers["retry-after"] = retry_after
    response = httpx.Response(
        status_code=status_code,
        headers=headers,
        request=httpx.Request("GET", "https://example.com"),
    )
    return httpx.HTTPStatusError(
        message=f"{status_code}", request=response.request, response=response
    )


def _make_retry_state(exception: BaseException, attempt: int = 1) -> RetryCallState:
    rs = RetryCallState(Retrying(), None, None, None)
    rs.attempt_number = attempt
    f = Future(attempt)
    f.set_exception(exception)
    rs.outcome = f
    return rs


class TestIsRetryablePlatformException:
    def test_connect_timeout(self):
        err = httpx.ConnectTimeout("timed out")
        assert is_retryable_platform_exception(err) is True

    def test_timeout_exception(self):
        err = httpx.TimeoutException("timed out")
        assert is_retryable_platform_exception(err) is True

    def test_enriched_408(self):
        http_err = _make_http_status_error(408)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is True

    def test_enriched_429(self):
        http_err = _make_http_status_error(429)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is True

    def test_enriched_502(self):
        http_err = _make_http_status_error(502)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is True

    def test_enriched_503(self):
        http_err = _make_http_status_error(503)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is True

    def test_enriched_504(self):
        http_err = _make_http_status_error(504)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is True

    def test_enriched_524_cloudflare_timeout(self):
        http_err = _make_http_status_error(524)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is True

    def test_enriched_400_not_retryable(self):
        http_err = _make_http_status_error(400)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is False

    def test_enriched_500_not_retryable(self):
        http_err = _make_http_status_error(500)
        err = EnrichedException(http_err)
        assert is_retryable_platform_exception(err) is False

    def test_raw_http_error_not_matched(self):
        err = _make_http_status_error(429)
        assert is_retryable_platform_exception(err) is False

    def test_unrelated_exception_not_retryable(self):
        assert is_retryable_platform_exception(ValueError("nope")) is False


class TestIsRetryableResponse:
    def test_500(self):
        assert is_retryable_response(httpx.Response(500)) is True

    def test_502(self):
        assert is_retryable_response(httpx.Response(502)) is True

    def test_503(self):
        assert is_retryable_response(httpx.Response(503)) is True

    def test_599(self):
        assert is_retryable_response(httpx.Response(599)) is True

    def test_200_not_retryable(self):
        assert is_retryable_response(httpx.Response(200)) is False

    def test_400_not_retryable(self):
        assert is_retryable_response(httpx.Response(400)) is False

    def test_429_not_retryable(self):
        assert is_retryable_response(httpx.Response(429)) is False


class TestPlatformWaitStrategy:
    def test_uses_retry_after_header(self):
        http_err = _make_http_status_error(429, retry_after="5")
        rs = _make_retry_state(http_err)
        assert platform_wait_strategy(rs) == 5.0

    def test_caps_retry_after_at_max(self):
        http_err = _make_http_status_error(429, retry_after="999")
        rs = _make_retry_state(http_err)
        assert platform_wait_strategy(rs) == _MAX_RETRY_AFTER_DELAY

    def test_falls_back_to_backoff_without_header(self):
        http_err = _make_http_status_error(503)
        rs = _make_retry_state(http_err, attempt=1)
        wait = platform_wait_strategy(rs)
        # attempt 1: 1.0 * 2^0 + jitter(0,1) = [1.0, 2.0)
        assert 1.0 <= wait < 2.0

    def test_backoff_capped_at_max(self):
        http_err = _make_http_status_error(503)
        # attempt 5: 1.0 * 2^4 = 16.0 + jitter, but capped at _MAX_BACKOFF_DELAY
        rs = _make_retry_state(http_err, attempt=5)
        assert platform_wait_strategy(rs) == _MAX_BACKOFF_DELAY

    def test_no_outcome_falls_back_to_backoff(self):
        rs = RetryCallState(Retrying(), None, None, None)
        rs.attempt_number = 1
        rs.outcome = None
        wait = platform_wait_strategy(rs)
        assert 1.0 <= wait < 2.0
