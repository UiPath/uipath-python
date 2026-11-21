"""The version 4 engine: its request manifest and its answer."""

import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from ..execution_types import (
    ExecuteActivityResult,
    ExecuteFile,
    ExecuteHttpResult,
    ExecuteResult,
)
from ._multipart import _file_part
from ._proxy_response import _flatten_headers, _is_int
from ._request import CONTENT_TYPE, JSON_CONTENT_TYPE, OCTET_STREAM, MultipartPart
from ._response_content import header_value

_V4_MAJOR_VERSION = 4
_MAJOR_VERSION_RE = re.compile(r"^v?(\d+)(?:\.|$)", re.IGNORECASE)
_MANIFEST_PART_NAME = "manifest"
_MULTIPART_MIXED = "multipart/mixed"
_BOUNDARY_RE = re.compile(r'boundary="?([^";]+)"?', re.IGNORECASE)
_CRLF = b"\r\n"
_HEADER_END = b"\r\n\r\n"


def uses_v4_engine(connector_version: Optional[str]) -> bool:
    """True when a connector of this version runs on the version 4 engine.

    That is major version 4 or later. A missing or unreadable version means
    the version 3 engine.
    """
    if not connector_version:
        return False
    match = _MAJOR_VERSION_RE.match(connector_version.strip())
    return match is not None and int(match.group(1)) >= _V4_MAJOR_VERSION


def _with_query(url: str, query_params: Optional[Dict[str, str]]) -> str:
    if not query_params:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(query_params)}"


def build_v4_manifest(
    *,
    connection_id: str,
    connector_key: Optional[str],
    method: str,
    url: str,
    headers: Optional[Dict[str, str]],
    query_params: Optional[Dict[str, str]],
    body: Any,
    file: Optional[ExecuteFile],
) -> Dict[str, Any]:
    """Build the version 4 request for one vendor call.

    The engine sends the body as given and has no query field, so query
    parameters join the URL and a serialized body is labelled as JSON.
    """
    request_headers = dict(headers or {})

    text: Optional[str] = None
    if body is not None:
        if isinstance(body, str):
            text = body
        else:
            text = json.dumps(body)
            if header_value(request_headers, CONTENT_TYPE) is None:
                request_headers["Content-Type"] = JSON_CONTENT_TYPE

    outbound: Dict[str, Any] = {"method": method, "url": _with_query(url, query_params)}
    if request_headers:
        outbound["headers"] = [
            {"name": name, "value": value} for name, value in request_headers.items()
        ]

    manifest: Dict[str, Any] = {"outboundRequestConfig": outbound}
    if file is not None:
        outbound["bodyRef"] = file.name
        manifest["attachments"] = [
            {
                "name": file.name,
                "size": len(file.content),
                "contentType": file.content_type or OCTET_STREAM,
            }
        ]
    elif text is not None:
        outbound["body"] = text

    context: Dict[str, Any] = {"connectionId": connection_id}
    if connector_key:
        context["connectorKey"] = connector_key
    manifest["context"] = context
    return manifest


def build_v4_activity_manifest(
    *,
    connection_id: str,
    connector_key: str,
    script_ref: str,
    body: Any,
    query_params: Optional[Dict[str, str]],
    headers: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """Build the version 4 request that runs one connector activity.

    The engine finds the activity's script by its reference and hands it the
    body, query and headers as the inbound call.
    """
    request: Dict[str, Any] = {}
    if body is not None:
        request["body"] = body
    if query_params:
        request["query"] = query_params
    if headers:
        request["headers"] = headers
    return {
        "context": {
            "connectionId": connection_id,
            "connectorKey": connector_key,
            "script": {"reference": script_ref},
        },
        "request": request,
    }


def to_v4_activity_result(result: ExecuteResult) -> ExecuteActivityResult:
    """Turn the version 4 engine's answer to an activity call into its result."""
    vendor = unwrap_v4_response(result)
    return ExecuteActivityResult(
        ok=vendor.ok,
        status=vendor.status,
        status_text=vendor.status_text,
        body=vendor.body,
        headers=vendor.headers,
    )


def build_v4_upload(manifest: Dict[str, Any], file: ExecuteFile) -> List[MultipartPart]:
    """The form of a version 4 call that uploads a file: the manifest, then the file."""
    return [
        (_MANIFEST_PART_NAME, ("blob", json.dumps(manifest), JSON_CONTENT_TYPE)),
        _file_part(file, file.file_name or file.name),
    ]


def unwrap_v4_response(result: ExecuteResult) -> ExecuteHttpResult:
    """Turn the version 4 engine's answer into the vendor's response.

    The engine answers 2xx whenever it reached the vendor and reports the
    vendor's status, headers and body inside the answer; any other status
    means the engine itself failed. The answer is a JSON object, or a two-part
    document (the same object without the body, then the bytes) when the
    vendor sent a file or a large body.
    """
    as_is = ExecuteHttpResult(**result.model_dump(), is_vendor_error=False)
    if not result.ok:
        return as_is

    if isinstance(result.body, (bytes, bytearray)):
        content_type = header_value(result.headers, CONTENT_TYPE) or ""
        if not content_type.lower().startswith(_MULTIPART_MIXED):
            return as_is
        envelope, content = _parse_two_part_answer(bytes(result.body), content_type)
        return _to_vendor_result(envelope, content)

    if not isinstance(result.body, dict) or not _is_int(result.body.get("status")):
        return as_is

    body = result.body.get("body")
    if result.body.get("bodyEncoding") == "base64" and isinstance(body, str):
        body = base64.b64decode(body)
    return _to_vendor_result(result.body, body)


def _to_vendor_result(envelope: Dict[str, Any], body: Any) -> ExecuteHttpResult:
    reported = envelope.get("status")
    status: int = reported if isinstance(reported, int) and _is_int(reported) else 0
    ok = 200 <= status < 300
    return ExecuteHttpResult(
        ok=ok,
        status=status,
        status_text="",
        body=body,
        headers=_flatten_headers(envelope.get("headers")),
        is_vendor_error=not ok,
    )


def _parse_two_part_answer(
    document: bytes, content_type: str
) -> Tuple[Dict[str, Any], bytes]:
    """Read the two-part answer: the JSON description, then the vendor's bytes.

    An answer without its closing delimiter was cut short and is refused.
    """

    def fail(reason: str) -> ValueError:
        return ValueError(
            f"Integration Service returned an incomplete file response: {reason}"
        )

    boundary_match = _BOUNDARY_RE.search(content_type)
    if not boundary_match:
        raise fail("no boundary")

    delimiter = f"--{boundary_match.group(1)}".encode("utf-8")
    closing = _CRLF + delimiter + b"--"

    first = document.find(delimiter)
    first_body_start = _end_of_headers(document, first)
    second = (
        document.find(_CRLF + delimiter, first_body_start)
        if first_body_start >= 0
        else -1
    )
    if first < 0 or first_body_start < 0 or second < 0:
        raise fail("first part not found")

    second_body_start = _end_of_headers(document, second + len(_CRLF))
    end = document.rfind(closing)
    if second_body_start < 0 or end < second_body_start:
        raise fail("closing delimiter not found")

    try:
        envelope = json.loads(document[first_body_start:second].decode("utf-8"))
    except ValueError as error:
        raise fail("first part is not JSON") from error
    if not isinstance(envelope, dict):
        raise fail("first part is not an object")

    return envelope, document[second_body_start:end]


def _end_of_headers(document: bytes, start: int) -> int:
    """Position just after the blank line that ends a part's headers, or -1."""
    if start < 0:
        return -1
    position = document.find(_HEADER_END, start)
    return -1 if position < 0 else position + len(_HEADER_END)
