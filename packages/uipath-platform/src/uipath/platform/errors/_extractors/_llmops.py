"""LLMOps service error payload extractor."""

from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._helpers import get_typed_field


def extract_llmops(body: dict[str, Any]) -> ExtractedErrorInfo:
    return ExtractedErrorInfo(
        message=get_typed_field(body, str, "errorMessage"),
        error_code=get_typed_field(body, str, "code"),
        trace_id=get_typed_field(body, str, "requestId"),
    )
