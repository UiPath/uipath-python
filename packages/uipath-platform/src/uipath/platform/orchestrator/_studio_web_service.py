"""StudioWeb service for UiPath Platform."""

import logging

import httpx

from ..common._http_config import get_httpx_client_kwargs

logger = logging.getLogger(__name__)


class StudioWebService:
    """Service for interacting with the UiPath StudioWeb API."""

    @staticmethod
    def enable_first_run(tenant_url: str, access_token: str) -> None:
        """Fire-and-forget POST requests to enable first run for StudioWeb.

        Posts to TryEnableFirstRun and AcquireLicense endpoints.

        Args:
            tenant_url: The tenant base URL (e.g., "https://cloud.uipath.com/org/tenant").
            access_token: The Bearer access token for authorization.
        """
        urls = [
            f"{tenant_url}/orchestrator_/api/StudioWeb/TryEnableFirstRun",
            f"{tenant_url}/orchestrator_/api/StudioWeb/AcquireLicense",
        ]
        headers = {"Authorization": f"Bearer {access_token}"}

        with httpx.Client(**get_httpx_client_kwargs()) as client:
            for url in urls:
                try:
                    response = client.post(url, headers=headers)
                    if not response.is_success:
                        logger.warning(
                            "StudioWeb enable_first_run: POST %s returned %s",
                            url,
                            response.status_code,
                        )
                except httpx.HTTPError as exc:
                    logger.warning(
                        "StudioWeb enable_first_run: POST %s failed: %s",
                        url,
                        exc,
                    )

    @staticmethod
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
