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

    Does not retain a reference to the original HTTPStatusError — all needed
    data is eagerly extracted. Callers needing the raw response can still
    access ``__cause__`` (set by ``raise EnrichedException(e) from e``).
    """

    def __init__(self, error: HTTPStatusError) -> None:
        # while status code 0 is the correct one according to http standard;
        # it has a totally oposite meaning as return codes in CLIs;
        # opted for -1 to avoid confusion
        self.status_code: int = error.response.status_code if error.response else -1
        self.url: str = str(error.request.url) if error.request else "Unknown"
        self.http_method: str = (
            error.request.method
            if error.request and error.request.method
            else "Unknown"
        )

        self._response_body: str | None = None
        self._content_type: str | None = None
        if error.response is not None:
            self._content_type = error.response.headers.get("content-type")
            if error.response.content:
                try:
                    self._response_body = error.response.content.decode("utf-8")
                except Exception:
                    pass

        max_content_length = 200
        if self._response_body:
            if len(self._response_body) > max_content_length:
                self.response_content = (
                    self._response_body[:max_content_length] + "... (truncated)"
                )
            else:
                self.response_content = self._response_body
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

        if not self._response_body:
            return None
        return extract_error_info(self.url, self._response_body, self._content_type)
