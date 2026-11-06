"""Model resolution for LLM-backed simulations."""

import os
from typing import Any

from uipath.platform.chat._llm_gateway_service import ChatModels
from uipath.runtime.schema import UiPathRuntimeSchema

from ._types import ModelSettings

SIMULATION_MODEL_ENV = "UIPATH_SIMULATION_MODEL"
# Output token limit of a simulation call. Reasoning models count their
# reasoning against it, so the chat service default (4096) is too low for long
# simulated responses; the cap bounds a runaway reply.
SIMULATION_MAX_TOKENS = 16384


def get_agent_max_tokens(schema: UiPathRuntimeSchema) -> int | None:
    """Get the agent's max tokens from the runtime schema metadata.

    Read from ``schema.metadata["settings"]``, where the low-code agents runtime
    puts the agent's settings (the model is read from there too).

    Returns:
        The agent's max tokens, or None if not found or not a positive integer.
    """
    settings = (schema.metadata or {}).get("settings")
    if not isinstance(settings, dict):
        return None
    max_tokens = settings.get("max_tokens", settings.get("maxTokens"))
    if isinstance(max_tokens, int) and not isinstance(max_tokens, bool):
        return max_tokens if max_tokens > 0 else None
    return None


def simulation_model_settings(
    model: str, agent_max_tokens: int | None = None
) -> ModelSettings:
    """Build the settings for a simulation that uses the agent's model.

    The output limit is the agent's own max tokens, a value the model is known
    to accept, capped at ``SIMULATION_MAX_TOKENS``.
    """
    max_tokens = SIMULATION_MAX_TOKENS
    if agent_max_tokens and agent_max_tokens > 0:
        max_tokens = min(agent_max_tokens, SIMULATION_MAX_TOKENS)
    return ModelSettings(model=model, maxTokens=max_tokens)


def simulation_completion_kwargs(
    model_settings: ModelSettings | None,
) -> dict[str, Any]:
    """Build completion kwargs for a simulation call, always naming the model."""
    completion_kwargs = (
        model_settings.model_dump(by_alias=False, exclude_none=True)
        if model_settings
        else {}
    )
    # Coded agents have no model in their schema; BYOM tenants block the default.
    completion_kwargs.setdefault(
        "model",
        os.environ.get(SIMULATION_MODEL_ENV) or ChatModels.gpt_4_1_mini_2025_04_14,
    )
    completion_kwargs.setdefault("max_tokens", SIMULATION_MAX_TOKENS)
    return completion_kwargs
