"""The request of an execute call: constants, endpoints and method checks."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

ELEMENT_INSTANCES_BASE = "/elements_/v3/element/instances"
ELEMENT_V4_EXECUTE = "/elements_/v4/execute"

EXECUTE_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
# RFC 9110 idempotent methods: a replayed POST can create the same record twice.
DEFAULT_RETRY_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})

JSON_CONTENT_TYPE = "application/json"
OCTET_STREAM = "application/octet-stream"
CONTENT_TYPE = "content-type"
CONTENT_DISPOSITION = "content-disposition"

MultipartPart = Tuple[str, Tuple[Optional[str], Any, Optional[str]]]


@dataclass
class ExecuteRequest:
    """One request against a connection instance."""

    method: str
    endpoint: str
    params: Optional[Dict[str, str]] = None
    body: Any = None
    has_body: bool = False
    files: Optional[List[MultipartPart]] = None
    file_response: bool = False
    folder_key: Optional[str] = None
    folder_path: Optional[str] = None
    max_retries: int = 0
    retryable: bool = False
    timeout: Optional[float] = None


def normalize_method(method: str, caller: str) -> str:
    """Upper-case and validate the HTTP method of an execute call."""
    normalized = (method or "").upper()
    if normalized not in EXECUTE_METHODS:
        raise ValueError(
            f"method must be one of {sorted(EXECUTE_METHODS)} for {caller}"
        )
    return normalized


def is_retryable_method(method: str, retry_methods: Optional[Sequence[str]]) -> bool:
    """True when a failed call with this method may be sent again."""
    allowed = (
        DEFAULT_RETRY_METHODS
        if retry_methods is None
        else {name.upper() for name in retry_methods}
    )
    return method in allowed


def activity_endpoint(connection_id: str, object_name: str) -> str:
    """Path of a connector object operation.

    `object_name` may be a multi-segment path such as `curated_get_issue/ABC-1`:
    each segment is encoded on its own and the `/` separators are kept.
    """
    path = "/".join(quote(segment, safe="") for segment in object_name.split("/"))
    return f"{ELEMENT_INSTANCES_BASE}/{quote(connection_id, safe='')}/{path}"


def http_request_endpoint(connection_id: str) -> str:
    """Path of the version 3 raw HTTP passthrough of a connection."""
    return f"{ELEMENT_INSTANCES_BASE}/{quote(connection_id, safe='')}/http-request"
