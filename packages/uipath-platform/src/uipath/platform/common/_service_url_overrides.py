"""Per-service URL overrides for local development.

Set UIPATH_SERVICE_URL_<SERVICE>=http://localhost:<port> to redirect
requests for a specific service to a local server. The service name
is derived from the endpoint prefix (e.g., agenthub_ -> AGENTHUB).

The local server receives only the API path — org/tenant prefix and
service prefix are stripped.

When an override is active, routing headers (X-UiPath-Internal-TenantId,
X-UiPath-Internal-AccountId) are injected since the platform routing
layer is bypassed.
"""

import os

from ._config import UiPathConfig


def resolve_service_url(endpoint_path: str) -> str | None:
    """Resolve a service URL override for the given endpoint path.

    Args:
        endpoint_path: Endpoint path with service prefix,
            e.g. "agenthub_/llm/api/chat/completions" or
            "/orchestrator_/odata/Buckets".

    Returns:
        Override URL with the API path appended, or None if no override is set.
    """
    path = endpoint_path.lstrip("/")
    if not path:
        return None

    first_segment = path.split("/")[0]
    if "_" not in first_segment:
        return None

    service_name = first_segment.replace("_", "").upper()
    override_base = os.getenv(f"UIPATH_SERVICE_URL_{service_name}")
    if not override_base:
        return None

    remaining = path[len(first_segment) :]
    return f"{override_base.rstrip('/')}{remaining}"


def inject_routing_headers(headers: dict[str, str]) -> None:
    """Add routing headers bypassed when using a local service override.

    The platform routing layer normally injects tenant and account
    identifiers. When going direct to a local service, these must
    be sent explicitly.

    Args:
        headers: Mutable headers dict to update in place.
    """
    tenant_id = UiPathConfig.tenant_id
    if tenant_id:
        headers["X-UiPath-Internal-TenantId"] = tenant_id

    organization_id = UiPathConfig.organization_id
    if organization_id:
        headers["X-UiPath-Internal-AccountId"] = organization_id
