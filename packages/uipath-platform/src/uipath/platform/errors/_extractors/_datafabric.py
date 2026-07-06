"""Data Fabric query engine error payload extractor.

DF returns: {"error": "<message>", "code": "<ERROR_CODE>", "traceId": "<uuid>"}
"""

from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._helpers import get_str_field, get_typed_field


def extract_datafabric(body: dict[str, Any]) -> ExtractedErrorInfo:
    message = get_typed_field(body, str, "error", "message")
    error_code = get_str_field(body, "code", "errorCode")
    trace_id = get_typed_field(body, str, "traceId", "requestId")

    return ExtractedErrorInfo(
        message=message,
        error_code=error_code,
        trace_id=trace_id,
    )
