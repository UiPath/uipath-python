"""Retry utilities for UiPath platform HTTP requests.

Provides generic, reusable retry helpers (status codes, header parsing, backoff)
and platform-specific retry strategy for BaseService.
"""

import random

from httpx import ConnectTimeout, HTTPStatusError, Response, TimeoutException
from tenacity import RetryCallState

from ..errors import EnrichedException

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 429, 502, 503, 504})


def parse_retry_after(header_value: str) -> float | None:
    """Parse a numeric Retry-After header value.

    Only handles numeric durations (seconds). HTTP-date values return None.
    Negative values return None.
    """
    try:
        seconds = float(header_value.strip())
        if seconds < 0:
            return None
        return seconds
    except (ValueError, AttributeError):
        return None


def exponential_backoff_with_jitter(attempt: int, initial: float) -> float:
    """Calculate exponential backoff with jitter.

    Returns ``initial * 2^(attempt-1) + uniform(0, 1.0)``.
    """
    exponent = attempt - 1
    exponential = initial * (2**exponent)
    jitter = random.uniform(0, 1.0)
    return exponential + jitter


def extract_retry_after_from_chain(exception: BaseException) -> float | None:
    """Walk the exception __cause__ chain looking for a Retry-After header.

    Supports ``HTTPStatusError`` (has ``.response.headers``) and
    ``EnrichedException`` whose ``__cause__`` is an ``HTTPStatusError``.
    """
    current: BaseException | None = exception
    while current is not None:
        if isinstance(current, HTTPStatusError):
            header = current.response.headers.get("retry-after")
            if header:
                parsed = parse_retry_after(header)
                if parsed is not None:
                    return parsed
        current = current.__cause__
    return None


MAX_RETRY_ATTEMPTS: int = 5
_MAX_RETRY_AFTER_DELAY: float = 120.0
_MAX_BACKOFF_DELAY: float = 10.0
_INITIAL_BACKOFF: float = 1.0


def is_retryable_platform_exception(exception: BaseException) -> bool:
    """Return True if the exception is transient and should be retried."""
    if isinstance(exception, (ConnectTimeout, TimeoutException)):
        return True
    if isinstance(exception, EnrichedException):
        return exception.status_code in RETRYABLE_STATUS_CODES
    return False


def is_retryable_response(response: Response) -> bool:
    """Return True if the response has a server error status code (5xx)."""
    return 500 <= response.status_code < 600


def platform_wait_strategy(retry_state: RetryCallState) -> float:
    """Wait strategy that honors Retry-After, falling back to exponential backoff."""
    if retry_state.outcome is not None:
        exception = retry_state.outcome.exception()
        if exception is not None:
            retry_after = extract_retry_after_from_chain(exception)
            if retry_after is not None:
                return min(retry_after, _MAX_RETRY_AFTER_DELAY)

    backoff = exponential_backoff_with_jitter(
        retry_state.attempt_number, _INITIAL_BACKOFF
    )
    return min(backoff, _MAX_BACKOFF_DELAY)
