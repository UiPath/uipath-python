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

    NORMALIZED_COMPLETION_ENDPOINT = "llmgateway_/api/chat/completions"
    PASSTHROUGH_COMPLETION_ENDPOINT = "llmgateway_/openai/deployments/{model}/chat/completions?api-version={api_version}"
    EMBEDDING_ENDPOINT = (
        "llmgateway_/openai/deployments/{model}/embeddings?api-version={api_version}"
    )


class EndpointManager:
    """Manages and caches the UiPath endpoints.
    This class provides functionality to determine which UiPath endpoints to use based on
    the availability of AgentHub. It checks for AgentHub capabilities and caches the result
    to avoid repeated network calls.
    Class Attributes:
        _base_url (str): The base URL for UiPath services, retrieved from the UIPATH_URL
                         environment variable.
        _agenthub_available (Optional[bool]): Cached result of AgentHub availability check.

    Methods:
        is_agenthub_available(): Checks if AgentHub is available, caching the result.
        get_passthrough_endpoint(): Returns the appropriate passthrough completion endpoint.
        get_normalized_endpoint(): Returns the appropriate normalized completion endpoint.
        get_embeddings_endpoint(): Returns the appropriate embeddings endpoint.
    All endpoint methods automatically select between AgentHub and standard endpoints
    based on availability.
    """  # noqa: D205

    _base_url = os.getenv("UIPATH_URL", "")
    _agenthub_available: Optional[bool] = None

    @classmethod
    def is_agenthub_available(cls) -> bool:
        """Check if AgentHub is available and cache the result."""
        if cls._agenthub_available is None:
            cls._agenthub_available = cls._check_agenthub()
        return cls._agenthub_available

    @classmethod
    def _check_agenthub(cls) -> bool:
        """Perform the actual check for AgentHub capabilities."""
        try:
            with httpx.Client(**get_httpx_client_kwargs()) as http_client:
                base_url = os.getenv("UIPATH_URL", "")
                capabilities_url = f"{base_url.rstrip('/')}/{UiPathEndpoints.AH_CAPABILITIES_ENDPOINT.value}"
                loggger.debug(f"Checking AgentHub capabilities at {capabilities_url}")
                response = http_client.get(capabilities_url)

                if response.status_code != 200:
                    return False

                capabilities = response.json()

                # Validate structure and required fields
                if not isinstance(capabilities, dict) or "version" not in capabilities:
                    return False

                return True

        except Exception as e:
            loggger.error(f"Error checking AgentHub capabilities: {e}", exc_info=True)
            return False

    @classmethod
    def get_passthrough_endpoint(cls) -> str:
        if cls.is_agenthub_available():
            return UiPathEndpoints.AH_PASSTHROUGH_COMPLETION_ENDPOINT.value

        return UiPathEndpoints.PASSTHROUGH_COMPLETION_ENDPOINT.value

    @classmethod
    def get_normalized_endpoint(cls) -> str:
        if cls.is_agenthub_available():
            return UiPathEndpoints.AH_NORMALIZED_COMPLETION_ENDPOINT.value

        return UiPathEndpoints.NORMALIZED_COMPLETION_ENDPOINT.value

    @classmethod
    def get_embeddings_endpoint(cls) -> str:
        if cls.is_agenthub_available():
            return UiPathEndpoints.AH_EMBEDDING_ENDPOINT.value

        return UiPathEndpoints.EMBEDDING_ENDPOINT.value
