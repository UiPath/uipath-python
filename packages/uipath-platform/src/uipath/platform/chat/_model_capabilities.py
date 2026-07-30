"""Per-model parameter support, resolved from the LLM Gateway discovery API.

Newer models reject parameters that older ones accept: passing `temperature` to
a model that dropped it fails the whole request with HTTP 400. The gateway
publishes these constraints per model under `modelDetails`, so callers can strip
the parameter instead of guessing from the model name.
"""

import logging
from typing import Any

from ..common._base_service import BaseService
from ..common._endpoints_manager import EndpointManager
from ..common._models import Endpoint
from ..constants import HEADER_AGENTHUB_CONFIG

logger = logging.getLogger(__name__)

CacheKey = tuple[str, str | None]

# One fetch per (base_url, agenthub_config); an empty mapping caches "couldn't read
# discovery". Deliberately unlocked: a racing duplicate GET is cheaper than an
# asyncio.Lock pinned to whichever event loop touched it first.
_model_details: dict[CacheKey, dict[str, dict[str, Any]]] = {}


async def should_skip_temperature(
    service: BaseService, model: str, agenthub_config: str | None
) -> bool:
    """Whether `model` rejects the `temperature` parameter.

    Args:
        service: Service used to call discovery; supplies base URL and auth.
        model: Model name as sent to the gateway.
        agenthub_config: AgentHub config scoping which models are visible.

    Returns:
        True only when discovery explicitly reports the model skips temperature.
        Unknown models, unreachable discovery, and any unexpected failure return
        False, leaving the caller's request untouched.
    """
    try:
        details = await _details_for(service, model, agenthub_config)
    except Exception as e:
        logger.warning(
            "Could not resolve parameter support for model %s (%s); "
            "sending model parameters unchanged",
            model,
            e,
        )
        return False

    return bool(details.get("shouldSkipTemperature", False))


async def _details_for(
    service: BaseService, model: str, agenthub_config: str | None
) -> dict[str, Any]:
    key = (service._config.base_url, agenthub_config)

    if key not in _model_details:
        _model_details[key] = await _fetch_model_details(service, agenthub_config)

    return _model_details[key].get(model, {})


async def _fetch_model_details(
    service: BaseService, agenthub_config: str | None
) -> dict[str, dict[str, Any]]:
    headers = {HEADER_AGENTHUB_CONFIG: agenthub_config} if agenthub_config else {}
    endpoint = Endpoint("/" + EndpointManager.get_discovery_endpoint())

    try:
        response = await service.request_async("GET", endpoint, headers=headers)
        models = response.json()
    except Exception as e:
        # Falling back to the caller's parameters is the pre-existing behaviour;
        # failing the LLM call because discovery is down would be worse.
        logger.warning(
            "LLM Gateway discovery unavailable (%s); sending model parameters unchanged",
            e,
        )
        return {}

    if not isinstance(models, list):
        logger.warning("Unexpected LLM Gateway discovery payload; expected a list")
        return {}

    return {
        model["modelName"]: model.get("modelDetails") or {}
        for model in models
        if isinstance(model, dict) and model.get("modelName")
    }


def _reset_cache() -> None:
    """Clear the discovery cache. For tests."""
    _model_details.clear()
