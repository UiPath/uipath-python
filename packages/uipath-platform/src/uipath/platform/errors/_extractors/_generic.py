"""Generic fallback error payload extractor.

Tries structural RFC 7807 detection first, then common field patterns
covering Orchestrator, Connections, ECS, and most other services.
"""

from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._helpers import get_field, get_str_field, get_typed_field
from ._rfc7807 import extract_rfc7807

_RFC7807_KEYS = {"type", "title", "status", "detail", "instance"}


def _looks_like_rfc7807(body: dict[str, Any]) -> bool:
    return len(_RFC7807_KEYS & body.keys()) >= 2


def extract_generic(body: dict[str, Any]) -> ExtractedErrorInfo:
    if _looks_like_rfc7807(body):
        return extract_rfc7807(body)

    message: str | None
    error = get_field(body, "error")
    if isinstance(error, str):
        message = error
    elif isinstance(error, dict):
        message = get_typed_field(error, str, "message")
    else:
        message = get_typed_field(body, str, "message")

    # str() conversion handles services that return numeric error codes
    error_code = get_str_field(body, "errorCode", "code")
    trace_id = get_typed_field(body, str, "traceId", "requestId")

    return ExtractedErrorInfo(
        message=message,
        error_code=error_code,
        trace_id=trace_id,
    )
