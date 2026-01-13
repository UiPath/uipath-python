"""Configurable runtime factory that supports model settings overrides."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from uipath.runtime import UiPathRuntimeFactoryProtocol, UiPathRuntimeProtocol

from ._models._evaluation_set import EvaluationSetModelSettings

logger = logging.getLogger(__name__)


class ConfigurableRuntimeFactory:
    """Wrapper factory that supports model settings overrides for evaluation runs.

    This factory wraps an existing UiPathRuntimeFactoryProtocol implementation
    and allows applying model settings overrides when creating runtimes.
    """

    def __init__(self, base_factory: UiPathRuntimeFactoryProtocol):
        """Initialize with a base factory to wrap."""
        self.base_factory = base_factory
        self.model_settings_override: EvaluationSetModelSettings | None = None
        self.input_overrides: dict[str, Any] = {}
        self._temp_files: list[str] = []

    def set_model_settings_override(
        self, settings: EvaluationSetModelSettings | None
    ) -> None:
        """Set model settings to override when creating runtimes.

        Args:
            settings: The model settings to apply, or None to clear overrides
        """
        self.model_settings_override = settings

    def set_input_overrides(self, overrides: dict[str, Any]) -> None:
        """Set input overrides per evaluation ID.

        Args:
            overrides: Dictionary mapping evaluation IDs to their override values.
                Format: {"eval-1": {"operator": "*"}, "eval-2": {"a": 100}}
                Supports deep merge for nested objects.
        """
        self.input_overrides = overrides

    async def new_runtime(
        self, entrypoint: str, runtime_id: str
    ) -> UiPathRuntimeProtocol:
        """Create a new runtime with optional model settings overrides.

        If model settings override is configured, creates a temporary modified
        entrypoint file with the overridden settings.

        Args:
            entrypoint: Path to the agent entrypoint file
            runtime_id: Unique identifier for the runtime instance

        Returns:
            A new runtime instance with overrides applied if configured
        """
        # If no overrides, delegate directly to base factory
        if not self.model_settings_override:
            return await self.base_factory.new_runtime(entrypoint, runtime_id)

        # Apply overrides by creating modified entrypoint
        modified_entrypoint = self._apply_overrides(
            entrypoint, self.model_settings_override
        )
        if modified_entrypoint:
            # Track temp file for cleanup
            self._temp_files.append(modified_entrypoint)
            return await self.base_factory.new_runtime(modified_entrypoint, runtime_id)

        # If override failed, fall back to original
        return await self.base_factory.new_runtime(entrypoint, runtime_id)

    def _apply_overrides(
        self, entrypoint: str, settings: EvaluationSetModelSettings
    ) -> str | None:
        """Apply model settings overrides to an agent entrypoint.

        Creates a temporary modified version of the entrypoint file with
        the specified model settings overrides applied.

        Args:
            entrypoint: Path to the original entrypoint file
            settings: Model settings to override

        Returns:
            Path to temporary modified entrypoint, or None if override not needed/failed
        """
        if (
            settings.model_name == "same-as-agent"
            and settings.temperature == "same-as-agent"
        ):
            logger.debug(
                "Both model and temperature are 'same-as-agent', no override needed"
            )
            return None

        entrypoint_path = Path(entrypoint)
        if not entrypoint_path.exists():
            logger.warning(f"Entrypoint file '{entrypoint_path}' not found")
            return None

        try:
            with open(entrypoint_path, "r") as f:
                agent_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load entrypoint file: {e}")
            return None

        original_settings = agent_data.get("settings", {})
        modified_settings = original_settings.copy()

        # Override model if not "same-as-agent"
        if settings.model_name != "same-as-agent":
            modified_settings["model"] = settings.model_name
            logger.debug(
                f"Overriding model: {original_settings.get('model')} -> {settings.model_name}"
            )

        # Override temperature if not "same-as-agent"
        if settings.temperature not in ["same-as-agent", None]:
            if isinstance(settings.temperature, (int, float)):
                modified_settings["temperature"] = float(settings.temperature)
            elif isinstance(settings.temperature, str):
                try:
                    modified_settings["temperature"] = float(settings.temperature)
                except ValueError:
                    logger.warning(
                        f"Invalid temperature value: '{settings.temperature}'"
                    )

            if "temperature" in modified_settings:
                logger.debug(
                    f"Overriding temperature: {original_settings.get('temperature')} -> "
                    f"{modified_settings['temperature']}"
                )

        if modified_settings == original_settings:
            return None

        agent_data["settings"] = modified_settings

        # Create a temporary file with the modified agent definition
        try:
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".json", prefix="agent_override_"
            )
            with os.fdopen(temp_fd, "w") as temp_file:
                json.dump(agent_data, temp_file, indent=2)

            logger.info(f"Created temporary entrypoint with overrides: {temp_path}")
            return temp_path
        except Exception as e:
            logger.error(f"Failed to create temporary entrypoint file: {e}")
            return None

    def apply_input_overrides(
        self, inputs: dict[str, Any], eval_id: str | None = None
    ) -> dict[str, Any]:
        """Apply input overrides to inputs using direct field override.

        Format: Per-evaluation overrides (keys are evaluation IDs):
           {"eval-1": {"operator": "*"}, "eval-2": {"a": 100}}

        Deep merge is supported for nested objects:
        - {"filePath": {"ID": "new-id"}} - deep merges inputs["filePath"] with {"ID": "new-id"}

        Args:
            inputs: The original inputs dictionary
            eval_id: The evaluation ID (required)

        Returns:
            A new dictionary with overrides applied
        """
        if not self.input_overrides:
            return inputs

        if not eval_id:
            logger.warning(
                "eval_id not provided, cannot apply input overrides. Input overrides require eval_id."
            )
            return inputs

        import copy

        result = copy.deepcopy(inputs)

        # Check if there are overrides for this specific eval_id
        if eval_id not in self.input_overrides:
            logger.debug(f"No overrides found for eval_id='{eval_id}'")
            return result

        overrides_to_apply = self.input_overrides[eval_id]
        logger.debug(
            f"Applying overrides for eval_id='{eval_id}': {overrides_to_apply}"
        )

        # Apply direct field overrides with recursive deep merge
        def deep_merge(
            base: dict[str, Any], override: dict[str, Any]
        ) -> dict[str, Any]:
            """Recursively merge override into base dictionary."""
            result = copy.deepcopy(base)
            for key, value in override.items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    # Recursively merge nested dicts
                    result[key] = deep_merge(result[key], value)
                else:
                    # Direct replacement for non-dict or new keys
                    result[key] = value
            return result

        for key, value in overrides_to_apply.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursive deep merge for dict values
                result[key] = deep_merge(result[key], value)
            else:
                # Direct replacement for non-dict or new keys
                result[key] = value

        return result

    async def dispose(self) -> None:
        """Dispose resources and clean up temporary files."""
        # Clean up any temporary files created
        for temp_file in self._temp_files:
            try:
                os.unlink(temp_file)
                logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")

        self._temp_files.clear()

        # Delegate disposal to base factory
        if hasattr(self.base_factory, "dispose"):
            await self.base_factory.dispose()
