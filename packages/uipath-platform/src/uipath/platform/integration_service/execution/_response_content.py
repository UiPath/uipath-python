"""Reading a response body: bytes for a file, parsed JSON, or text."""

import json
import logging
from typing import Any, Mapping, Optional

from httpx import Response

from ..execution_types import (
    ExecuteResult,
)
from ._request import CONTENT_DISPOSITION, CONTENT_TYPE

logger: logging.Logger = logging.getLogger("uipath")


# Content types that carry data to read, even when marked as an attachment.
_DATA_CONTENT_TYPES = (
    "application/json",
    "application/xml",
    "text/xml",
    "text/csv",
    "text/plain",
    "application/atom+xml",
    "application/rss+xml",
)

_BINARY_CONTENT_TYPE_PREFIXES = (
    "application/octet-stream",
    "application/pdf",
    "application/zip",
    "image/",
    "audio/",
    "video/",
    "application/vnd.",
    "application/x-tar",
    "application/gzip",
    # A multipart answer is framed bytes; whoever asked for it parses it
    "multipart/",
)


def header_value(headers: Mapping[str, str], name: str) -> Optional[str]:
    """Read a header from a flat mapping whatever the case of its name."""
    direct = headers.get(name)
    if direct is not None:
        return direct
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _is_data_content_type(content_type: str) -> bool:
    essence = content_type.split(";")[0].strip()
    if essence.startswith(_DATA_CONTENT_TYPES):
        return True
    # Structured suffixes such as application/vnd.api+json are data, image/svg+xml is not
    is_text_tree = essence.startswith(("application/", "text/"))
    return is_text_tree and essence.endswith(("+json", "+xml"))


def is_file_response(headers: Mapping[str, str]) -> bool:
    """True when the response headers describe a file instead of data to parse.

    That is: the content type is not a data type, and the response is an
    attachment or has a binary content type.
    """
    content_type = (header_value(headers, CONTENT_TYPE) or "").lower()
    if _is_data_content_type(content_type):
        return False

    disposition = (header_value(headers, CONTENT_DISPOSITION) or "").lower()
    return "attachment" in disposition or content_type.startswith(
        _BINARY_CONTENT_TYPE_PREFIXES
    )


def to_result(response: Response, as_file: bool = False) -> ExecuteResult:
    """Read a response into its envelope, whatever its status.

    The body is `bytes` for a file, parsed JSON when the text is JSON, and the
    text otherwise. `as_file` reads a 2xx response as bytes whatever its
    content type.
    """
    headers = dict(response.headers)

    body: Any
    if (as_file and response.is_success) or is_file_response(headers):
        body = response.content
    else:
        body = response.text
        if body:
            try:
                body = json.loads(body)
            except ValueError:
                logger.debug("execute: response body is not JSON, returning text")

    return ExecuteResult(
        ok=response.is_success,
        status=response.status_code,
        status_text=response.reason_phrase,
        body=body,
        headers=headers,
    )
