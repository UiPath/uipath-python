"""LLM Gateway error payload extractor."""

from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._helpers import get_typed_field


def extract_llm_gateway(body: dict[str, Any]) -> ExtractedErrorInfo:
    message = get_typed_field(body, str, "message")
    error_code = get_typed_field(body, str, "errorCode", "code")
    trace_id = get_typed_field(body, str, "traceId")

    error = get_typed_field(body, dict, "error")
    if error is not None:
        message = message or get_typed_field(error, str, "message")
        error_code = error_code or get_typed_field(error, str, "code", "type")

    return ExtractedErrorInfo(
        message=message,
        error_code=error_code,
        trace_id=trace_id,
    )
