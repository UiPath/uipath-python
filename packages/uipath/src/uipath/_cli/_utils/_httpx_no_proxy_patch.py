import ipaddress
import logging
import os

logger = logging.getLogger(__name__)


def _is_unparseable_by_httpx(entry: str) -> bool:
    if "://" in entry:
        return False
    if entry.startswith("["):
        return True
    if "/" not in entry:
        return False
    try:
        ipaddress.IPv6Address(entry.split("/", 1)[0])
    except ValueError:
        return False
    return True


def remove_unsupported_no_proxy_entries() -> None:
    """Remove NO_PROXY entries that make httpx fail to create a client.

    httpx raises InvalidURL for IPv6 ranges (fc00::/7) and bracketed IPv6
    addresses ([::1]). See https://github.com/encode/httpx/issues/3221.
    """
    for variable in ("NO_PROXY", "no_proxy"):
        value = os.environ.get(variable)
        if not value:
            continue
        kept: list[str] = []
        removed: list[str] = []
        for entry in value.split(","):
            (removed if _is_unparseable_by_httpx(entry.strip()) else kept).append(entry)
        if not removed:
            continue
        os.environ[variable] = ",".join(kept)
        logger.warning(
            "Removed %s from %s: httpx cannot parse these entries.",
            ",".join(e.strip() for e in removed),
            variable,
        )
