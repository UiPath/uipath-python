"""Query parameters that take a URL, sent Base64-encoded."""

import base64
import re
from typing import Dict, Optional, Sequence
from urllib.parse import unquote, urlsplit

# Paging parameters. Their values are tokens the connector reads as they are.
_RESERVED_QUERY_KEYS = frozenset({"pagesize", "nextpage", "page", "providernextpage"})
_ARRAY_MARKER_RE = re.compile(r"\[\*]$")


def looks_like_url(value: str) -> bool:
    """True when `value` is an http or https URL, plain or percent-encoded once."""
    try:
        parts = urlsplit(unquote(value))
    except ValueError:
        return False
    return parts.scheme.lower() in ("http", "https") and bool(parts.netloc)


def encode_url_inputs(
    query: Optional[Dict[str, str]], fields: Optional[Sequence[str]]
) -> Optional[Dict[str, str]]:
    """Base64-encode the query values that carry a URL.

    Integration Service rejects a request whose query holds an encoded slash,
    so for the fields a connector marks as accepting a URL the value travels
    as Base64 and the connector decodes it. A value is encoded only when its
    name is listed and it is an http or https URL. Names match without regard
    to case, and paging parameters are never encoded.
    """
    if not query or not fields:
        return query

    flagged = {_ARRAY_MARKER_RE.sub("", name).lower() for name in fields}

    encoded: Optional[Dict[str, str]] = None
    for key, value in query.items():
        name = key.lower()
        if (
            name in _RESERVED_QUERY_KEYS
            or name not in flagged
            or not isinstance(value, str)
            or not looks_like_url(value)
        ):
            continue
        if encoded is None:
            encoded = dict(query)
        encoded[key] = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return query if encoded is None else encoded
