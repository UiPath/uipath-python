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


_RFC7807_REQUIRED = {"detail", "title"}
_RFC7807_SUPPORTING = {"type", "status", "instance"}


def is_rfc7807_content_type(content_type: str | None) -> bool:
    """Check if the content type indicates an RFC 7807 response."""
    if not content_type:
        return False
    return content_type.split(";")[0].strip().lower() in _RFC7807_CONTENT_TYPES


def looks_like_rfc7807(body: dict[str, Any]) -> bool:
    """Structural heuristic: has detail/title + at least 2 RFC 7807 keys."""
    keys = body.keys()
    has_required = bool(_RFC7807_REQUIRED & keys)
    supporting_count = len((_RFC7807_REQUIRED | _RFC7807_SUPPORTING) & keys)
    return has_required and supporting_count >= 2


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
