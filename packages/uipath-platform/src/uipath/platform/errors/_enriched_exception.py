from dataclasses import dataclass
from functools import cached_property

from httpx import HTTPStatusError


@dataclass(frozen=True)
class ExtractedErrorInfo:
    message: str | None = None
    error_code: str | None = None
    trace_id: str | None = None


class EnrichedException(Exception):
    """Enriched HTTP error with detailed request/response information.

    Wraps HTTPStatusError with URL, method, status code, and truncated response
    content in __str__. For structured error fields, use ``error_info`` which
    delegates to per-service extractors.
    """

    def __init__(self, error: HTTPStatusError) -> None:
        self._http_error = error
        self.status_code: int = error.response.status_code if error.response else 0
        self.url: str = str(error.request.url) if error.request else "Unknown"
        self.http_method: str = (
            error.request.method
            if error.request and error.request.method
            else "Unknown"
        )
        max_content_length = 200
        if error.response and error.response.content:
            content = error.response.content.decode("utf-8")
            if len(content) > max_content_length:
                self.response_content = content[:max_content_length] + "... (truncated)"
            else:
                self.response_content = content
        else:
            self.response_content = "No content"

        enriched_message = (
            f"\nRequest URL: {self.url}"
            f"\nHTTP Method: {self.http_method}"
            f"\nStatus Code: {self.status_code}"
            f"\nResponse Content: {self.response_content}"
        )

        super().__init__(enriched_message)

    @cached_property
    def error_info(self) -> ExtractedErrorInfo | None:
        """Service-aware extraction of message, error_code, trace_id."""
        from ._extractors._router import extract_error_info

        resp = self._http_error.response
        if resp is None or not resp.content:
            return None
        try:
            body = resp.content.decode("utf-8")
        except Exception:
            return None
        content_type = resp.headers.get("content-type") if resp is not None else None
        return extract_error_info(self.url, body, content_type)
