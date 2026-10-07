"""Business Rules service error payload extractor.

Business Rules returns: {"error": {"code": "<ERROR_CODE>", "message": "<message>"},
"meta": {...}}, with the code nested under "error" where the generic extractor
does not look for it.
"""

from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._generic import extract_generic
from ._helpers import get_field, get_str_field, get_typed_field


def extract_businessrules(body: dict[str, Any]) -> ExtractedErrorInfo:
    error_envelope = get_field(body, "error")
    if not isinstance(error_envelope, dict):
        # Not the service's envelope, e.g. an error answered by the gateway.
        return extract_generic(body)

    return ExtractedErrorInfo(
        message=get_typed_field(error_envelope, str, "message"),
        error_code=get_str_field(error_envelope, "code"),
        trace_id=get_typed_field(body, str, "traceId", "requestId"),
    )
