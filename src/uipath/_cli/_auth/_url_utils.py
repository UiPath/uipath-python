import os
from urllib.parse import urlparse

ignore_env_var = False


def get_base_url(domain: str) -> str:
    """Get the base URL for UiPath services.

    Args:
        domain: Either a domain name (e.g., 'cloud', 'alpha') or a full URL from UIPATH_URL

    Returns:
        The base URL to use for UiPath services
    """
    global ignore_env_var

    if not ignore_env_var:
        # If UIPATH_URL is set and domain is 'cloud' (default), use the base from UIPATH_URL
        uipath_url = os.getenv("UIPATH_URL")
        if uipath_url and domain == "cloud":
            parsed_url = urlparse(uipath_url)
            return f"{parsed_url.scheme}://{parsed_url.netloc}"

    # If domain is already a full URL, use it directly
    if domain.startswith("http"):
        return domain

    # Otherwise, construct the URL using the domain
    return f"https://{domain if domain else 'cloud'}.uipath.com"


def set_force_flag(force: bool):
    global ignore_env_var
    ignore_env_var = force


def build_service_url(domain: str, path: str) -> str:
    """Build a service URL by combining the base URL with a path.

    Args:
        domain: Either a domain name or full URL
        path: The path to append (should start with /)

    Returns:
        The complete service URL
    """
    base_url = get_base_url(domain)
    # Remove trailing slash from base_url to avoid double slashes
    base_url = base_url.rstrip("/")
    return f"{base_url}{path}"
