import json
import logging
from functools import cached_property
from pathlib import Path
from typing import Any, overload

from ._bindings import ResourceOverwrite, _resource_overwrites
from ._config import UiPathConfig

logger = logging.getLogger(__name__)


class BindingsService:
    """Service for reading bindings configurations from bindings.json.

    Provides access to properties configured at design time and resolved at runtime.
    """

    def __init__(self, bindings_file_path: Path | None = None) -> None:
        self._bindings_file_path = bindings_file_path or UiPathConfig.bindings_file_path

    @cached_property
    def _load_bindings(self) -> list[dict[str, Any]]:
        try:
            with open(self._bindings_file_path, "r") as f:
                data = json.load(f)
            return data.get("resources", [])
        except FileNotFoundError:
            logger.debug("Bindings file not found: %s", self._bindings_file_path)
            return []
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to load bindings file %s: %s", self._bindings_file_path, e
            )
            return []

    def _find_resource(self, key: str) -> dict[str, Any] | None:
        """Find a binding resource by exact or suffix key match."""
        resources = self._load_bindings
        for resource in resources:
            resource_key = resource.get("key", "")
            if (
                resource_key == key
                or resource_key.endswith(f".{key}")
                or resource_key.endswith(key)
            ):
                return resource
        return None

    def _get_overwrite(self, key: str) -> ResourceOverwrite | None:
        """Check context var for a runtime overwrite for the given key.

        Supports exact key match and suffix match so that
        a short label like ``"SharePoint Invoices folder"`` resolves against a
        fully-qualified stored key like
        ``"property.sharepoint-connection.SharePoint Invoices folder"``.
        """
        context_overwrites = _resource_overwrites.get()
        if context_overwrites is None:
            return None
        for stored_key, overwrite in context_overwrites.items():
            # Remove the `<resource_type>.` prefix correctly
            parts = stored_key.split(".", 1)
            bare_key = parts[1] if len(parts) > 1 else stored_key

            if bare_key == key or bare_key.endswith(f".{key}") or stored_key == key:
                return overwrite
        return None

    @overload
    def get_property(self, key: str) -> dict[str, str]: ...

    @overload
    def get_property(self, key: str, sub_property: str) -> str: ...

    def get_property(
        self, key: str, sub_property: str | None = None
    ) -> str | dict[str, str]:
        """Get the value(s) of a binding resource.

        Args:
            key: The binding key, e.g. ``"sharepoint-connection.SharePoint Invoices folder"`` or ``"asset.my-asset"``.
            Accepts the full key or a suffix that uniquely identifies the binding.
            sub_property: The name of a specific sub-property to retrieve (e.g. ``"ID"`` or ``"folderPath"``).
            If omitted, returns all sub-properties as a ``{name: value}`` dict.        Returns:
            The ``defaultValue`` of the requested sub-property when ``sub_property`` is
            given, or a dict of all sub-property names mapped to their ``defaultValue``
            when ``sub_property`` is omitted.

        Raises:
            KeyError: When the binding key is not found, or when ``sub_property`` is given
                but does not exist on the binding.
        """
        # Check for runtime overwrite first
        overwrite = self._get_overwrite(key)
        if overwrite is not None:
            if sub_property is not None:
                if sub_property not in overwrite.properties:
                    raise KeyError(
                        f"Sub-property '{sub_property}' not found in binding '{key}'. "
                        f"Available: {list(overwrite.properties.keys())}"
                    )
                return overwrite.properties[sub_property]
            return dict(overwrite.properties)

        # Fall back to bindings.json
        resource = self._find_resource(key)
        if resource is None:
            raise KeyError(
                f"Binding '{key}' not found in {self._bindings_file_path}."
            )

        value: dict = resource.get("value", {})
        all_values = {
            name: props.get("defaultValue", "") if isinstance(props, dict) else str(props)
            for name, props in value.items()
        }

        if sub_property is not None:
            if sub_property not in all_values:
                raise KeyError(
                    f"Sub-property '{sub_property}' not found in binding '{key}'. "
                    f"Available: {list(all_values.keys())}"
                )
            return all_values[sub_property]

        return all_values
