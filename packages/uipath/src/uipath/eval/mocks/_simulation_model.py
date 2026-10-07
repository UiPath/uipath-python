"""Model resolution for LLM-backed simulations."""

import os
from typing import Any

from uipath.platform.chat._llm_gateway_service import ChatModels

from ._types import ModelSettings

SIMULATION_MODEL_ENV = "UIPATH_SIMULATION_MODEL"


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
    return completion_kwargs
