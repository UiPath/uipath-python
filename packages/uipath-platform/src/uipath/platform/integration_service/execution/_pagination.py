"""Paging state of a list response and following the connector's pages."""

import base64
import binascii
import json
import math
from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional

from ..execution_types import (
    ExecuteActivityResult,
    ExecutePage,
    ExecuteResult,
)
from ._request import ExecuteRequest
from ._response_content import header_value

HAS_MORE_HEADER = "elements-has-more"
NEXT_PAGE_TOKEN_HEADER = "elements-next-page-token"
NEXT_PAGE_PARAM = "nextPage"

_ALL_RECORDS = -1
# Marker a connector puts in its page token once the list is exhausted.
_PROVIDER_DONE = "DONE"


def resolve_max_records(max_records: Optional[int], caller: str) -> Optional[float]:
    """Turn the caller's `max_records` into the record limit to page up to.

    Returns None when paging is off and `math.inf` for every record.
    """
    if max_records is None:
        return None
    if isinstance(max_records, bool) or not isinstance(max_records, int):
        raise ValueError(f"max_records must be a positive integer or -1 for {caller}")
    if max_records == _ALL_RECORDS:
        return math.inf
    if max_records <= 0:
        raise ValueError(f"max_records must be a positive integer or -1 for {caller}")
    return max_records


def _is_token_exhausted(token: str) -> bool:
    """A page token is base64url JSON; the connector marks the end of the list in it."""
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, binascii.Error):
        # An unreadable token is still a usable token.
        return False
    if not isinstance(decoded, dict):
        return False
    provider_next_page = decoded.get("providerNextPage")
    return (
        isinstance(provider_next_page, str)
        and provider_next_page.upper() == _PROVIDER_DONE
    )


def extract_page(headers: Mapping[str, str], body: Any) -> Optional[ExecutePage]:
    """Read the paging state of a list response.

    Returns None when the response is not a paged list or the connector
    reported its last page.
    """
    has_more = header_value(headers, HAS_MORE_HEADER)
    next_page_token = header_value(headers, NEXT_PAGE_TOKEN_HEADER)
    if not has_more or not next_page_token or not isinstance(body, list):
        return None
    if _is_token_exhausted(next_page_token):
        return None
    return ExecutePage(
        has_more=has_more.lower() == "true", next_page_token=next_page_token
    )


def strip_pagination_headers(headers: Mapping[str, str]) -> Dict[str, str]:
    """Drop the paging headers, for a result whose pages were already gathered."""
    dropped = (HAS_MORE_HEADER, NEXT_PAGE_TOKEN_HEADER)
    return {key: value for key, value in headers.items() if key.lower() not in dropped}


def to_activity_result(result: ExecuteResult) -> ExecuteActivityResult:
    """Add the paging state to a single-page result when the connector reported one."""
    return ExecuteActivityResult(
        **result.model_dump(), page=extract_page(result.headers, result.body)
    )


def next_page_request(request: ExecuteRequest, page: ExecutePage) -> ExecuteRequest:
    """The request for the page a token points to."""
    params = dict(request.params or {})
    params[NEXT_PAGE_PARAM] = page.next_page_token
    return replace(request, params=params)


def needs_paging(
    method: str, max_records: Optional[float], first: ExecuteResult
) -> bool:
    """True when `max_records` asks the call to follow the connector's pages."""
    return (
        max_records is not None
        and method == "GET"
        and first.ok
        and isinstance(first.body, list)
    )


def gathered_result(
    first: ExecuteResult,
    last: ExecuteResult,
    records: List[Any],
    max_records: float,
    followed: bool,
) -> ExecuteActivityResult:
    """The result of a call that followed pages: every record gathered, as one list."""
    if not followed and len(records) <= max_records:
        return to_activity_result(first)
    limit = len(records) if max_records == math.inf else int(max_records)
    return ExecuteActivityResult(
        ok=last.ok,
        status=last.status,
        status_text=last.status_text,
        body=records[:limit],
        headers=strip_pagination_headers(last.headers),
    )
