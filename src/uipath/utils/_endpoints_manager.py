import logging
import os
from enum import Enum
from typing import Any, Dict, Optional

import httpx

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
    """Manages and caches the UiPath endpoints."""

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
            with httpx.Client() as http_client:
                base_url = os.getenv("UIPATH_URL", "")
                capabilities_url = f"{base_url.rstrip('/')}/{UiPathEndpoints.AH_CAPABILITIES_ENDPOINT.value}"
                loggger.debug(f"Checking AgentHub capabilities at {capabilities_url}")
                response = http_client.get(capabilities_url)
                return response.status_code == 200
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
