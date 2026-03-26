"""Utility for retrieving the Orchestrator server version."""

from typing import Any

import httpx

from ..common._http_config import get_httpx_client_kwargs


def get_server_version(domain: str) -> str | None:
    """Get the Orchestrator server version.

    Args:
        domain: The base URL of the UiPath platform (e.g., "https://cloud.uipath.com").

    Returns:
        The server version string, or None if the request fails for any reason.
    """
    url = f"{domain}/orchestrator_/api/status/version"

    try:
        client_kwargs = get_httpx_client_kwargs()
        client_kwargs["timeout"] = 5.0
        with httpx.Client(**client_kwargs) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("version")
    except Exception:
        return None


async def get_server_info_async(domain: str) -> dict[Any, Any] | None:
    """Get the full Orchestrator server status info.

    Args:
        domain: The base URL of the UiPath platform (e.g., "https://cloud.uipath.com").

    Returns:
        The full server status JSON as a dict, or None if the request fails for any reason.
    """
    url = f"{domain}/orchestrator_/api/status/version"

    try:
        client_kwargs = get_httpx_client_kwargs()
        client_kwargs["timeout"] = 5.0
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception:
        return None


async def get_server_version_async(domain: str) -> str | None:
    """Get the Orchestrator server version.

    Args:
        domain: The base URL of the UiPath platform (e.g., "https://cloud.uipath.com").

    Returns:
        The server version string, or None if the request fails for any reason.
    """
    url = f"{domain}/orchestrator_/api/status/version"

    try:
        client_kwargs = get_httpx_client_kwargs()
        client_kwargs["timeout"] = 5.0
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("version")
    except Exception:
        return None
