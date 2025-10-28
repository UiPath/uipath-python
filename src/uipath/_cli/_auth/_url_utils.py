import os
from typing import Optional, Tuple
from urllib.parse import urlparse

from .._utils._console import ConsoleLogger

console = ConsoleLogger()


def resolve_domain(
    base_url: Optional[str], cloud_url: Optional[str], force: bool = False
) -> str:
    """Resolve the UiPath domain, giving priority to base_url when valid.

    Args:
        base_url: The base URL explicitly provided.
        cloud_url: The cloud URL from the --cloud option.
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

    # If base_url is not set (or force is False), check UIPATH_URL
    if not base_url or not force:
        uipath_url = os.getenv("UIPATH_URL")
        if uipath_url and cloud_url == "https://cloud.uipath.com":
            parsed = urlparse(uipath_url)
            if parsed.scheme and parsed.netloc:
                domain = f"{parsed.scheme}://{parsed.netloc}"
                return domain
            else:
                console.error(
                    f"Malformed UIPATH_URL: '{uipath_url}'. "
                    "Please ensure it includes scheme and netloc (e.g., 'https://cloud.uipath.com')."
                )

    # Otherwise, use the cloud_url directly
    if cloud_url:
        parsed = urlparse(cloud_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        else:
            console.error(
                f"Malformed cloud URL: '{cloud_url}'. "
                "Please ensure it includes scheme and netloc (e.g., 'https://cloud.uipath.com')."
            )

    # Fallback to production
    return "https://cloud.uipath.com"


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
