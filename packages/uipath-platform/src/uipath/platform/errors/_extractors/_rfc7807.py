"""RFC 7807 Problem Details error payload extractor."""

from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._helpers import get_typed_field

_RFC7807_CONTENT_TYPES = frozenset(
    {
        "application/problem+json",
        "application/problem+xml",
    }
)


def is_rfc7807_content_type(content_type: str | None) -> bool:
    """Check if the content type indicates an RFC 7807 response."""
    if not content_type:
        return False
    return content_type.split(";")[0].strip().lower() in _RFC7807_CONTENT_TYPES


def extract_rfc7807(body: dict[str, Any]) -> ExtractedErrorInfo:
    message = get_typed_field(body, str, "detail") or get_typed_field(
        body, str, "title"
    )
    error_code = get_typed_field(body, str, "type")
    trace_id = get_typed_field(body, str, "traceId", "instance")

    return ExtractedErrorInfo(
        message=message,
        error_code=error_code,
        trace_id=trace_id,
    )
