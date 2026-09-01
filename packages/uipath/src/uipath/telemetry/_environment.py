"""Resolve which UiPath environment a run reports telemetry to.

Derived from the base URL ``uipath auth`` writes to ``.env``, so authenticating
against alpha reports to alpha. An unrecognized host falls back to production,
which covers unauthenticated runs, Automation Suite and custom domains.
"""

import os
from typing import Literal
from urllib.parse import urlparse

from uipath.platform.constants import ENV_BASE_URL

UiPathEnvironment = Literal["alpha", "staging", "cloud"]

DEFAULT_ENVIRONMENT: UiPathEnvironment = "cloud"

_ENVIRONMENT_BY_DOMAIN: dict[str, UiPathEnvironment] = {
    "alpha.uipath.com": "alpha",
    "staging.uipath.com": "staging",
    "cloud.uipath.com": "cloud",
}


def _is_domain_or_subdomain(hostname: str, domain: str) -> bool:
    """Whether ``hostname`` is ``domain`` or a dot-separated subdomain of it."""
    return hostname == domain or hostname.endswith(f".{domain}")


def environment_from_base_url(base_url: str | None) -> UiPathEnvironment:
    """Map a UiPath base URL to its environment, defaulting to production."""
    if not base_url:
        return DEFAULT_ENVIRONMENT

    try:
        hostname = urlparse(base_url).hostname
    except ValueError:
        return DEFAULT_ENVIRONMENT

    if not hostname:
        return DEFAULT_ENVIRONMENT

    for domain, environment in _ENVIRONMENT_BY_DOMAIN.items():
        if _is_domain_or_subdomain(hostname, domain):
            return environment

    return DEFAULT_ENVIRONMENT


def resolve_environment() -> UiPathEnvironment:
    """Resolve the environment from the ambient ``UIPATH_URL``."""
    return environment_from_base_url(os.getenv(ENV_BASE_URL))
