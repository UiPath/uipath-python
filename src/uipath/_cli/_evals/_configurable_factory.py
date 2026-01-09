"""Configurable runtime factory that supports model settings overrides."""

import json
import logging
import os
import tempfile
from pathlib import Path

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
        self._temp_files: list[str] = []

    def set_model_settings_override(
        self, settings: EvaluationSetModelSettings | None
    ) -> None:
        """Set model settings to override when creating runtimes.

        Args:
            settings: The model settings to apply, or None to clear overrides
        """
        self.model_settings_override = settings

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
