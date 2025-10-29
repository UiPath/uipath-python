"""Bindings module for managing UiPath resource bindings.

This module provides a simple interface for accessing resource bindings
configured in uipath.json.
"""

import json
from pathlib import Path
from typing import Optional, Tuple


class Bindings:
    """Provides access to resource bindings configured in uipath.json.

    This class allows you to retrieve resource names and folder paths
    using binding keys defined in your uipath.json configuration file.

    Example:
        ```python
        from uipath import UiPath
        from uipath.bindings import Bindings

        client = UiPath()

        # Get asset name from binding
        asset_name = Bindings.get("my-asset")
        client.assets.retrieve(name=asset_name)

        # Get asset with folder path
        asset_name, folder_path = Bindings.get_with_folder("my-asset")
        client.assets.retrieve(name=asset_name, folder_path=folder_path)
        ```
    """

    _config_path: Path = Path("uipath.json")
    _cache: Optional[dict] = None

    @classmethod
    def _load_config(cls) -> dict:
        """Load the uipath.json configuration file.

        Returns:
            The configuration dictionary.

        Raises:
            FileNotFoundError: If uipath.json doesn't exist.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        if cls._cache is not None:
            return cls._cache

        if not cls._config_path.exists():
            raise FileNotFoundError(
                f"'{cls._config_path}' not found. Please run 'uipath init' first."
            )

        with open(cls._config_path, "r") as f:
            cls._cache = json.load(f)

        return cls._cache

    @classmethod
    def _get_overwrites(cls) -> dict:
        """Get the resourceOverwrites section from the config.

        Returns:
            The resourceOverwrites dictionary.
        """
        config = cls._load_config()
        return (
            config.get("runtime", {})
            .get("internalArguments", {})
            .get("resourceOverwrites", {})
        )

    @classmethod
    def get(
        cls, binding_key: str, resource_type: str = "asset", default: Optional[str] = None
    ) -> str:
        """Get the resource name for a binding key.

        Args:
            binding_key: The binding key defined in uipath.json.
            resource_type: The type of resource (asset, process, queue). Defaults to "asset".
            default: Default value to return if the binding is not found. If None and
                    binding is not found, raises KeyError.

        Returns:
            The resource name.

        Raises:
            KeyError: If the binding key is not found and no default is provided.
            FileNotFoundError: If uipath.json doesn't exist.

        Example:
            ```python
            from uipath.bindings import Bindings

            # Get asset name
            asset_name = Bindings.get("my-asset")

            # Get with default
            asset_name = Bindings.get("my-asset", default="DefaultAssetName")

            # Get process name
            process_name = Bindings.get("my-process", resource_type="process")
            ```
        """
        overwrites = cls._get_overwrites()
        full_key = f"{resource_type}.{binding_key}"

        if full_key not in overwrites:
            if default is not None:
                return default
            raise KeyError(
                f"Binding '{binding_key}' for resource type '{resource_type}' not found in uipath.json. "
                f"Use 'uipath bindings create {binding_key} -t {resource_type} -n <name>' to create it."
            )

        return overwrites[full_key].get("name", binding_key)

    @classmethod
    def get_with_folder(
        cls,
        binding_key: str,
        resource_type: str = "asset",
        default: Optional[Tuple[str, Optional[str]]] = None,
    ) -> Tuple[str, Optional[str]]:
        """Get the resource name and folder path for a binding key.

        Args:
            binding_key: The binding key defined in uipath.json.
            resource_type: The type of resource (asset, process, queue). Defaults to "asset".
            default: Default tuple (name, folder_path) to return if the binding is not found.
                    If None and binding is not found, raises KeyError.

        Returns:
            A tuple of (resource_name, folder_path). folder_path can be None if not configured.

        Raises:
            KeyError: If the binding key is not found and no default is provided.
            FileNotFoundError: If uipath.json doesn't exist.

        Example:
            ```python
            from uipath.bindings import Bindings

            # Get asset name and folder
            asset_name, folder_path = Bindings.get_with_folder("my-asset")
            client.assets.retrieve(name=asset_name, folder_path=folder_path)

            # Get with default
            name, folder = Bindings.get_with_folder("my-asset", default=("DefaultAsset", None))
            ```
        """
        overwrites = cls._get_overwrites()
        full_key = f"{resource_type}.{binding_key}"

        if full_key not in overwrites:
            if default is not None:
                return default
            raise KeyError(
                f"Binding '{binding_key}' for resource type '{resource_type}' not found in uipath.json. "
                f"Use 'uipath bindings create {binding_key} -t {resource_type} -n <name>' to create it."
            )

        binding = overwrites[full_key]
        return binding.get("name", binding_key), binding.get("folderPath", None)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached configuration.

        This is useful if you've modified uipath.json and want to reload it.

        Example:
            ```python
            from uipath.bindings import Bindings

            # Clear cache to reload config
            Bindings.clear_cache()
            asset_name = Bindings.get("my-asset")
            ```
        """
        cls._cache = None

    @classmethod
    def set_config_path(cls, path: str | Path) -> None:
        """Set a custom path to the uipath.json file.

        Args:
            path: Path to the uipath.json file.

        Example:
            ```python
            from uipath.bindings import Bindings

            # Use a different config file
            Bindings.set_config_path("/path/to/my/uipath.json")
            asset_name = Bindings.get("my-asset")
            ```
        """
        cls._config_path = Path(path)
        cls._cache = None
