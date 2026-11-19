"""Request building and response reading for Integration Service execution.

Pure helpers behind `IntegrationService.execute_activity` and
`IntegrationService.execute_http`. Nothing here performs I/O.
"""

from ._body_paths import expand_body_paths
from ._multipart import build_multipart, validate_files
from ._pagination import (
    extract_page,
    gathered_result,
    needs_paging,
    next_page_request,
    resolve_max_records,
    to_activity_result,
)
from ._proxy_response import build_proxy_body, unwrap_proxy_response
from ._request import (
    BODY_METHODS,
    ELEMENT_V4_EXECUTE,
    ExecuteRequest,
    activity_endpoint,
    http_request_endpoint,
    is_retryable_method,
    normalize_method,
)
from ._response_content import is_file_response, to_result
from ._url_input import encode_url_inputs, looks_like_url
from ._v4_execute import (
    build_v4_activity_manifest,
    build_v4_manifest,
    build_v4_upload,
    to_v4_activity_result,
    unwrap_v4_response,
    uses_v4_engine,
)

__all__ = [
    "BODY_METHODS",
    "ELEMENT_V4_EXECUTE",
    "ExecuteRequest",
    "activity_endpoint",
    "build_multipart",
    "build_proxy_body",
    "build_v4_activity_manifest",
    "build_v4_manifest",
    "build_v4_upload",
    "encode_url_inputs",
    "expand_body_paths",
    "extract_page",
    "gathered_result",
    "http_request_endpoint",
    "is_file_response",
    "is_retryable_method",
    "looks_like_url",
    "needs_paging",
    "next_page_request",
    "normalize_method",
    "resolve_max_records",
    "to_activity_result",
    "to_result",
    "to_v4_activity_result",
    "unwrap_proxy_response",
    "unwrap_v4_response",
    "uses_v4_engine",
    "validate_files",
]
