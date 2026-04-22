"""Elements service error payload extractor."""

from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._helpers import get_str_field, get_typed_field


def extract_elements(body: dict[str, Any]) -> ExtractedErrorInfo:
    message = get_typed_field(body, str, "providerMessage") or get_typed_field(
        body, str, "message"
    )
    error_code = get_str_field(body, "providerErrorCode", "status")
    trace_id = get_typed_field(body, str, "requestId")

    return ExtractedErrorInfo(
        message=message,
        error_code=error_code,
        trace_id=trace_id,
    )
