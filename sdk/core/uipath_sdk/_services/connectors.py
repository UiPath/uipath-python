import importlib.metadata
import logging
from typing import Any, Dict

from .._config import Config
from .._execution_context import ExecutionContext
from ._base_service import BaseService

logger: logging.Logger = logging.getLogger("uipath")

ENTRYPOINT = "uipath_connectors"


class PluginNotFoundError(AttributeError):
    """Raised when a plugin is not installed or failed to load."""

    pass


class Connectors(BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

        self._plugins: Dict[str, Any] = {}
        self._plugins_loaded = False
        self._load_connectors()

    def __getattr__(self, name: str) -> Any:
        """Get a plugin by name.

        Args:
            name: The name of the plugin to get

        Returns:
            The plugin instance

        Raises:
            PluginNotFoundError: If the plugin is not installed
            ImportError: If the plugin fails to load
        """
        if not self._plugins_loaded:
            self._load_connectors()

        if name in self._plugins:
            return self._plugins[name]

        try:
            plugin: Any = getattr(self.client, name)
            self._plugins[name] = plugin
            return plugin
        except AttributeError as e:
            raise PluginNotFoundError(f"Plugin '{name}' is not installed") from e

    def _load_connectors(self) -> None:
        """Load all available connector plugins.

        Raises:
            ImportError: If a plugin fails to load
        """
        try:
            entry_points: Dict[str, list[importlib.metadata.EntryPoint]] = (
                importlib.metadata.entry_points()
            )
            if hasattr(entry_points, "select"):
                connectors = list(entry_points.select(group=ENTRYPOINT))
            else:
                connectors = list(entry_points.get(ENTRYPOINT, []))

            for entry_point in connectors:
                try:
                    register_func = entry_point.load()
                    register_func(self)
                except Exception as e:
                    logger.error(
                        f"[ERROR] Failed to load plugin {entry_point.name}: {str(e)}"
                    )

            self._plugins_loaded = True
        except Exception as e:
            self._plugins_loaded = False
            raise ImportError(f"Failed to load plugins: {str(e)}") from e
