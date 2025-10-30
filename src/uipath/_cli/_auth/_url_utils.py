import os
from typing import Optional, Tuple
from urllib.parse import urlparse

from .._utils._console import ConsoleLogger

console = ConsoleLogger()


def resolve_domain(base_url: Optional[str], environment: Optional[str]) -> str:
    """Resolve the UiPath domain, giving priority to base_url when valid.

    Args:
        base_url: The base URL explicitly provided.
        environment: The environment name (e.g., 'alpha', 'staging', 'cloud').
        force: Whether to ignore UIPATH_URL from environment variables when base_url is set.

    Returns:
        A valid base URL for UiPath services.
    """
    # If base_url is a real URL, prefer it
    if base_url and base_url.startswith("http"):
        parsed = urlparse(base_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain:
            return domain

    if environment is None:
        uipath_url = os.getenv("UIPATH_URL")
        if uipath_url:
            parsed = urlparse(uipath_url)
            if parsed.scheme and parsed.netloc:
                domain = f"{parsed.scheme}://{parsed.netloc}"
                return domain
            else:
                console.error(
                    f"Malformed UIPATH_URL: '{uipath_url}'. "
                    "Please ensure it includes scheme and netloc (e.g., 'https://cloud.uipath.com')."
                )

    # Otherwise, fall back to environment
    return f"https://{environment or 'cloud'}.uipath.com"


def build_service_url(domain: str, path: str) -> str:
    """Build a service URL by combining the base URL with a path.

    Args:
        domain: The domain name
        path: The path to append (should start with /)

    Returns:
        The complete service URL
    """
    return f"{domain}{path}"


def extract_org_tenant(uipath_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract organization and tenant from a UiPath URL.

    Accepts values like:
      - https://cloud.uipath.com/myOrg/myTenant
      - https://alpha.uipath.com/myOrg/myTenant/anything_else
      - cloud.uipath.com/myOrg/myTenant  (scheme will be assumed https)

    Args:
        uipath_url: The UiPath URL to parse

    Returns:
        A tuple of (organization, tenant) where:
          - organization: 'myOrg' or None
          - tenant: 'myTenant' or None

    Example:
        >>> extract_org_tenant('https://cloud.uipath.com/myOrg/myTenant')
        ('myOrg', 'myTenant')
    """
    parsed = urlparse(uipath_url if "://" in uipath_url else f"https://{uipath_url}")
    parts = [p for p in parsed.path.split("/") if p]
    org = parts[0] if len(parts) >= 1 else None
    tenant = parts[1] if len(parts) >= 2 else None
    return org, tenant
