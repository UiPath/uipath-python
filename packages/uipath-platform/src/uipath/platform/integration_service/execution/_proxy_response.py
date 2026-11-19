"""The version 3 HTTP passthrough: its request body and its answer."""

import json
from typing import Any, Dict, Optional

from ..execution_types import (
    ExecuteHttpResult,
    ExecuteResult,
)


def build_proxy_body(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]],
    query_params: Optional[Dict[str, str]],
    body: Any,
) -> Dict[str, Any]:
    """The request the version 3 passthrough accepts for one vendor call."""
    payload: Dict[str, Any] = {"method": method, "url": url}
    if headers is not None:
        payload["headers"] = headers
    if query_params is not None:
        payload["query"] = query_params
    if body is not None:
        # Integration Service takes the vendor body as a string
        payload["body"] = body if isinstance(body, str) else json.dumps(body)
    return payload


def unwrap_proxy_response(result: ExecuteResult) -> ExecuteHttpResult:
    """Turn the answer to a version 3 passthrough call into the vendor's response.

    Integration Service answers 200 whatever the vendor said and reports the
    vendor's status, headers and body inside the response body. When the call
    never reached the vendor (the answer is not 2xx, or carries no vendor
    status), the Integration Service response is returned as is.
    """
    envelope = result.body
    if (
        not result.ok
        or not isinstance(envelope, dict)
        or not _is_int(envelope.get("code"))
    ):
        return ExecuteHttpResult(**result.model_dump(), is_vendor_error=False)

    code = envelope["code"]
    ok = 200 <= code < 300
    status_text = envelope.get("statusText")
    body = envelope.get("body")
    return ExecuteHttpResult(
        ok=ok,
        status=code,
        status_text=status_text if isinstance(status_text, str) else "",
        # The parsed body wins; `rawStringBody` carries a vendor body that is not JSON.
        body=body if body is not None else envelope.get("rawStringBody"),
        headers=_flatten_headers(envelope.get("headers")),
        is_vendor_error=not ok,
    )


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _flatten_headers(value: Any) -> Dict[str, str]:
    """One string per header name; a repeated header arrives as a list."""
    if not isinstance(value, dict):
        return {}
    headers: Dict[str, str] = {}
    for name, entry in value.items():
        if entry is None:
            continue
        if isinstance(entry, list):
            headers[name] = ", ".join(str(item) for item in entry)
        else:
            headers[name] = str(entry)
    return headers
