"""Models for running connector activities and vendor HTTP requests.

Used by `IntegrationService.execute_activity` and `IntegrationService.execute_http`.
"""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel

ExecuteMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
"""HTTP method of an execute call."""


class ExecuteFile(BaseModel):
    """A file sent with an `execute_activity` or `execute_http` call."""

    name: str
    """Name of the form part the connector reads the file from, e.g. `file`."""
    content: bytes
    """The file's bytes."""
    file_name: Optional[str] = None
    """File name reported to the connector."""
    content_type: Optional[str] = None
    """Content type of the file. Defaults to `application/octet-stream`."""


class ExecutePage(BaseModel):
    """Where a paged list stands after an `execute_activity` call."""

    has_more: bool
    """True when the connector has more records after this page."""
    next_page_token: str
    """Token for the next page. Pass it as the `nextPage` query parameter."""


class ExecuteResult(BaseModel):
    """The HTTP envelope of an execute call.

    Unlike most SDK methods, an execute call does not raise on a non-2xx
    response: Integration Service proxies third-party calls, and the body
    carries the vendor's error details. Check `ok` and `status`.
    """

    ok: bool
    """True for an HTTP 2xx response."""
    status: int
    """HTTP status code."""
    status_text: str = ""
    """HTTP reason phrase."""
    body: Any = None
    """Parsed JSON when the response is JSON, the raw text otherwise, `bytes` for a file."""
    headers: Dict[str, str] = {}
    """Response headers."""


class ExecuteActivityResult(ExecuteResult):
    """Result of `IntegrationService.execute_activity`."""

    page: Optional[ExecutePage] = None
    """Paging state of a list response.

    None when the response is not a paged list, when the connector reported
    its last page, or when `max_records` already gathered the pages.
    """


class ExecuteHttpResult(ExecuteResult):
    """Result of `IntegrationService.execute_http`.

    `ok`, `status`, `status_text`, `headers` and `body` describe the vendor's
    response, not the Integration Service call that carried it.
    """

    is_vendor_error: bool = False
    """True when the vendor answered with a non-2xx status.

    False when the call failed before reaching the vendor, in which case the
    fields describe the Integration Service response.
    """
