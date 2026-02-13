"""Service URL override resolution for local development.

Allows routing specific service requests to alternative URLs (e.g., localhost)
via environment variables like ``UIPATH_ORCHESTRATOR_URL``.
"""

import os
from functools import lru_cache

# Maps environment variable suffix to the endpoint prefix used in request paths.
# E.g. UIPATH_ORCHESTRATOR_URL -> orchestrator_/
_SERVICE_PREFIX_MAP: dict[str, str] = {
    "ORCHESTRATOR": "orchestrator_",
    "AGENTHUB": "agenthub_",
    "DU": "du_",
    "ECS": "ecs_",
    "CONNECTIONS": "connections_",
    "DATAFABRIC": "datafabric_",
    "RESOURCECATALOG": "resourcecatalog_",
    "AGENTSRUNTIME": "agentsruntime_",
    "APPS": "apps_",
    "IDENTITY": "identity_",
    "STUDIO": "studio_",
}


@lru_cache(maxsize=1)
def _load_service_overrides() -> dict[str, str]:
    """Scan environment for ``UIPATH_{SERVICE}_URL`` variables.

    Returns:
        Mapping of endpoint prefix (e.g. ``orchestrator_``) to override URL.
    """
    overrides: dict[str, str] = {}
    for suffix, prefix in _SERVICE_PREFIX_MAP.items():
        value = os.environ.get(f"UIPATH_{suffix}_URL")
        if value:
            overrides[prefix] = value.rstrip("/")
    return overrides


def get_service_override(endpoint_prefix: str) -> str | None:
    """Look up a URL override for the given endpoint prefix.

    Args:
        endpoint_prefix: The service endpoint prefix (e.g. ``orchestrator_``).
            Lookup is case-insensitive.

    Returns:
        The override URL if configured, otherwise ``None``.
    """
    overrides = _load_service_overrides()
    return overrides.get(endpoint_prefix.lower())


def clear_overrides_cache() -> None:
    """Clear the cached overrides. Intended for tests."""
    _load_service_overrides.cache_clear()
