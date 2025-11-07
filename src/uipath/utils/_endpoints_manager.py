import logging
import os
from enum import Enum
from typing import Optional

import httpx

from uipath._utils._ssl_context import get_httpx_client_kwargs

loggger = logging.getLogger(__name__)


class UiPathEndpoints(Enum):
    AH_NORMALIZED_COMPLETION_ENDPOINT = "agenthub_/llm/api/chat/completions"
    AH_PASSTHROUGH_COMPLETION_ENDPOINT = "agenthub_/llm/openai/deployments/{model}/chat/completions?api-version={api_version}"
    AH_EMBEDDING_ENDPOINT = (
        "agenthub_/llm/openai/deployments/{model}/embeddings?api-version={api_version}"
    )
    AH_CAPABILITIES_ENDPOINT = "agenthub_/llm/api/capabilities"

    OR_NORMALIZED_COMPLETION_ENDPOINT = "orchestrator_/llm/api/chat/completions"
    OR_PASSTHROUGH_COMPLETION_ENDPOINT = "orchestrator_/llm/openai/deployments/{model}/chat/completions?api-version={api_version}"
    OR_EMBEDDING_ENDPOINT = "orchestrator_/llm/openai/deployments/{model}/embeddings?api-version={api_version}"
    OR_CAPABILITIES_ENDPOINT = "orchestrator_/llm/api/capabilities"


class EndpointManager:
    """Manages and caches the UiPath endpoints.
    This class provides functionality to determine which UiPath endpoints to use based on
    the availability of AgentHub and Orchestrator. It checks for capabilities and caches
    the results to avoid repeated network calls.

    The endpoint selection follows a fallback order:
    1. AgentHub (if available)
    2. Orchestrator (if available)

    Environment Variable Override:
    The fallback behavior can be bypassed using the UIPATH_LLM_SERVICE environment variable:
    - 'agenthub' or 'ah': Force use of AgentHub endpoints (skips capability checks)
    - 'orchestrator' or 'or': Force use of Orchestrator endpoints (skips capability checks)

    Class Attributes:
        _base_url (str): The base URL for UiPath services, retrieved from the UIPATH_URL
                         environment variable.
        _agenthub_available (Optional[bool]): Cached result of AgentHub availability check.
        _orchestrator_available (Optional[bool]): Cached result of Orchestrator availability check.

    Methods:
        is_agenthub_available(): Checks if AgentHub is available, caching the result.
        is_orchestrator_available(): Checks if Orchestrator is available, caching the result.
        get_passthrough_endpoint(): Returns the appropriate passthrough completion endpoint.
        get_normalized_endpoint(): Returns the appropriate normalized completion endpoint.
        get_embeddings_endpoint(): Returns the appropriate embeddings endpoint.
    All endpoint methods automatically select the best available endpoint using the fallback order,
    unless overridden by the UIPATH_LLM_SERVICE environment variable.
    """  # noqa: D205

    _base_url = os.getenv("UIPATH_URL", "")
    _agenthub_available: Optional[bool] = None
    _orchestrator_available: Optional[bool] = None

    @classmethod
    def is_agenthub_available(cls) -> bool:
        """Check if AgentHub is available and cache the result."""
        if cls._agenthub_available is None:
            cls._agenthub_available = cls._check_agenthub()
        return cls._agenthub_available

    @classmethod
    def is_orchestrator_available(cls) -> bool:
        """Check if Orchestrator is available and cache the result."""
        if cls._orchestrator_available is None:
            cls._orchestrator_available = cls._check_orchestrator()
        return cls._orchestrator_available

    @classmethod
    def _check_capabilities(cls, endpoint: UiPathEndpoints, service_name: str) -> bool:
        """Perform the actual check for service capabilities.

        Args:
            endpoint: The capabilities endpoint to check
            service_name: Human-readable service name for logging

        Returns:
            bool: True if the service is available and has valid capabilities
        """
        try:
            with httpx.Client(**get_httpx_client_kwargs()) as http_client:
                base_url = os.getenv("UIPATH_URL", "")
                capabilities_url = f"{base_url.rstrip('/')}/{endpoint.value}"
                loggger.debug(
                    f"Checking {service_name} capabilities at {capabilities_url}"
                )
                response = http_client.get(capabilities_url)

                if response.status_code != 200:
                    return False

                capabilities = response.json()

                # Validate structure and required fields
                if not isinstance(capabilities, dict) or "version" not in capabilities:
                    return False

                return True

        except Exception as e:
            loggger.error(
                f"Error checking {service_name} capabilities: {e}", exc_info=True
            )
            return False

    @classmethod
    def _check_agenthub(cls) -> bool:
        """Perform the actual check for AgentHub capabilities."""
        return cls._check_capabilities(
            UiPathEndpoints.AH_CAPABILITIES_ENDPOINT, "AgentHub"
        )

    @classmethod
    def _check_orchestrator(cls) -> bool:
        """Perform the actual check for Orchestrator capabilities."""
        return cls._check_capabilities(
            UiPathEndpoints.OR_CAPABILITIES_ENDPOINT, "Orchestrator"
        )

    @classmethod
    def _select_endpoint(cls, ah: UiPathEndpoints, orc: UiPathEndpoints) -> str:
        """Select an endpoint based on UIPATH_LLM_SERVICE override or capability checks."""
        service_override = os.getenv("UIPATH_LLM_SERVICE", "").lower()

        if service_override in ("agenthub", "ah"):
            return ah.value
        if service_override in ("orchestrator", "or"):
            return orc.value

        # Determine fallback order based on environment hints
        hdens_env = os.getenv("HDENS_ENV", "").lower()

        # Default order: AgentHub -> Orchestrator
        check_order = [
            ("ah", ah, cls.is_agenthub_available),
            ("orc", orc, cls.is_orchestrator_available),
        ]

        # Prioritize Orchestrator if HDENS_ENV is 'sf'
        # Note: The default order already prioritizes AgentHub
        if hdens_env == "sf":
            check_order.reverse()

        # Execute fallback checks in the determined order
        for _, endpoint, is_available in check_order:
            if is_available():
                return endpoint.value

        url = os.getenv("UIPATH_URL", "")
        if ".uipath.com" in url:
            return ah.value
        else:
            return orc.value

    @classmethod
    def get_passthrough_endpoint(cls) -> str:
        """Get the passthrough completion endpoint."""
        return cls._select_endpoint(
            UiPathEndpoints.AH_PASSTHROUGH_COMPLETION_ENDPOINT,
            UiPathEndpoints.OR_PASSTHROUGH_COMPLETION_ENDPOINT,
        )

    @classmethod
    def get_normalized_endpoint(cls) -> str:
        """Get the normalized completion endpoint."""
        return cls._select_endpoint(
            UiPathEndpoints.AH_NORMALIZED_COMPLETION_ENDPOINT,
            UiPathEndpoints.OR_NORMALIZED_COMPLETION_ENDPOINT,
        )

    @classmethod
    def get_embeddings_endpoint(cls) -> str:
        """Get the embeddings endpoint."""
        return cls._select_endpoint(
            UiPathEndpoints.AH_EMBEDDING_ENDPOINT,
            UiPathEndpoints.OR_EMBEDDING_ENDPOINT,
        )
