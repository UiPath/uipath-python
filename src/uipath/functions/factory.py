"""UiPath Functions Runtime Factory - discovery and creation of function-based runtimes."""

import json
import logging
from pathlib import Path
from typing import Any

from uipath.runtime import (
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    UiPathRuntimeStorageProtocol,
)

from .debug import UiPathDebugFunctionsRuntime
from .runtime import UiPathFunctionsRuntime

logger = logging.getLogger(__name__)


class UiPathFunctionsRuntimeFactory:
    """Factory for discovering and creating function-based runtimes."""

    def __init__(self, config_path: str = "uipath.json", base_dir: str | None = None):
        """Initialize the factory with the path to uipath.json configuration."""
        self.config_path = Path(config_path)
        self.base_dir = Path(base_dir) if base_dir else self.config_path.parent
        self._config: dict[str, Any] | None = None

    def _load_config(self) -> dict[str, Any]:
        """Load uipath.json configuration with caching."""
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return {}

        try:
            with open(self.config_path) as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.config_path}: {e}")
            return {}

        return self._config

    def discover_entrypoints(self) -> list[str]:
        """Discover all function entrypoints from uipath.json."""
        config = self._load_config()
        return list(config.get("functions", {}).keys())

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        """Get storage protocol if any (placeholder for protocol compliance)."""
        return None

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        """Get factory settings for coded functions.

        Coded functions don't need span filtering - all spans are relevant
        since developers have full control over instrumentation.

        Low-code agents (LangGraph) need filtering due to framework overhead.
        """
        return None

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs
    ) -> UiPathRuntimeProtocol:
        """Create a new runtime instance for the given entrypoint."""
        return self._create_runtime(entrypoint)

    async def dispose(self) -> None:
        """Dispose resources if any (placeholder for interface compliance)."""
        pass

    def _create_runtime(self, entrypoint: str) -> UiPathRuntimeProtocol:
        """Create runtime instance from entrypoint specification."""
        config = self._load_config()
        functions = config.get("functions", {})

        if entrypoint not in functions:
            raise ValueError(
                f"Entrypoint '{entrypoint}' not found in uipath.json. "
                f"Available: {', '.join(functions.keys())}"
            )

        func_spec = functions[entrypoint]

        if ":" not in func_spec:
            raise ValueError(
                f"Invalid function specification: '{func_spec}'. "
                "Expected format: 'path/to/file.py:function_name'"
            )

        file_path, function_name = func_spec.rsplit(":", 1)
        full_path = self.base_dir / file_path

        if not full_path.exists():
            raise ValueError(f"File not found: {full_path}")

        inner = UiPathFunctionsRuntime(str(full_path), function_name, entrypoint)
        return UiPathDebugFunctionsRuntime(
            delegate=inner,
            entrypoint_path=str(full_path),
            function_name=function_name,
        )
