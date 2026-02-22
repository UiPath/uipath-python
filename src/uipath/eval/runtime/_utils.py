"""Utility functions for applying input overrides to evaluation inputs."""

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base dictionary.

    Args:
        base: The base dictionary to merge into
        override: The override dictionary to merge from

    Returns:
        A new dictionary with overrides recursively merged into base
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = deep_merge(result[key], value)
        else:
            # Direct replacement for non-dict or new keys
            result[key] = value
    return result


def apply_input_overrides(
    inputs: dict[str, Any],
    input_overrides: dict[str, Any],
    eval_id: str | None = None,
) -> dict[str, Any]:
    """Apply input overrides to inputs using direct field override.

    Format: Per-evaluation overrides (keys are evaluation IDs):
       {"eval-1": {"operator": "*"}, "eval-2": {"a": 100}}

    Deep merge is supported for nested objects:
    - {"filePath": {"ID": "new-id"}} - deep merges inputs["filePath"] with {"ID": "new-id"}

    Args:
        inputs: The original inputs dictionary
        input_overrides: Dictionary mapping evaluation IDs to their override values
        eval_id: The evaluation ID (required)

    Returns:
        A new dictionary with overrides applied
    """
    if not input_overrides:
        return inputs

    if not eval_id:
        logger.warning(
            "eval_id not provided, cannot apply input overrides. Input overrides require eval_id."
        )
        return inputs

    result = copy.deepcopy(inputs)

    # Check if there are overrides for this specific eval_id
    if eval_id not in input_overrides:
        logger.debug(f"No overrides found for eval_id='{eval_id}'")
        return result

    overrides_to_apply = input_overrides[eval_id]
    logger.debug(f"Applying overrides for eval_id='{eval_id}': {overrides_to_apply}")

    # Apply direct field overrides with recursive deep merge
    for key, value in overrides_to_apply.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursive deep merge for dict values
            result[key] = deep_merge(result[key], value)
        else:
            # Direct replacement for non-dict or new keys
            result[key] = value

    return result
