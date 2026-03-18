"""Routes HTTP error payloads to the appropriate service extractor.

Priority:
1. RFC 7807 via content-type (authoritative)
2. LLM Gateway via URL path (/llm/)
3. Dedicated service extractor via URL prefix
4. Generic fallback (structural RFC 7807 + common fields)
"""

import json
from collections.abc import Callable
from typing import Any

from .._enriched_exception import ExtractedErrorInfo
from ._agenthub import extract_agenthub
from ._apps import extract_apps
from ._elements import extract_elements
from ._generic import extract_generic
from ._helpers import extract_service_prefix, is_llm_path
from ._llm_gateway import extract_llm_gateway
from ._llmops import extract_llmops
from ._rfc7807 import extract_rfc7807, is_rfc7807_content_type

_Extractor = Callable[[dict[str, Any]], ExtractedErrorInfo]

# Only services with extraction logic that differs from generic.
# All other services (orchestrator, connections, ecs, etc.) fall through to generic.
_SERVICE_EXTRACTORS: dict[str, _Extractor] = {
    "agenthub_": extract_agenthub,
    "agentsruntime_": extract_agenthub,
    "apps_": extract_apps,
    "elements_": extract_elements,
    "llmopstenant_": extract_llmops,
}


def extract_error_info(
    url: str,
    body: str,
    content_type: str | None = None,
) -> ExtractedErrorInfo | None:
    """Parse an HTTP error response body into structured error info.

    Returns None if the body cannot be parsed as JSON.
    """
    try:
        parsed: dict[str, Any] = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(parsed, dict):
        return None

    if is_rfc7807_content_type(content_type):
        return extract_rfc7807(parsed)

    if is_llm_path(url):
        return extract_llm_gateway(parsed)

    prefix = extract_service_prefix(url)
    if prefix is not None:
        extractor = _SERVICE_EXTRACTORS.get(prefix)
        if extractor is not None:
            return extractor(parsed)

    return extract_generic(parsed)
