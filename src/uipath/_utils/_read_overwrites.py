import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple


class OverwritesManager:
    """Manages overwrites for different resource types and methods.

    This class handles reading and accessing bindings overwrites from a JSON file.
    The overwrites are stored under the 'resourceOverwrites' key, where each key is a
    resource key (e.g., 'asset.MyAssetKeyFromBindingsJson') and the value contains
    'name' and 'folderPath' fields.

    This is a singleton class to ensure only one instance exists throughout the application.
    """

    _instance = None
    _overwrites_file_path: Path = Path("__uipath/uipath.json")
    _runtime_overwrites: Dict[str, Any] = {}

    def __new__(
        cls, overwrites_file_path: Optional[Path] = None
    ) -> "OverwritesManager":
        """Create or return the singleton instance.

        Args:
            overwrites_file_path: Optional path to the overwrites JSON file.
                If not provided, defaults to 'uipath.json' in the project root.

        Returns:
            The singleton instance of OverwritesManager.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._overwrites_file_path = (
                overwrites_file_path or cls._overwrites_file_path
            )
            cls._instance._read_overwrites_file()
        elif (
            overwrites_file_path
            and overwrites_file_path != cls._instance._overwrites_file_path
        ):
            # If a new file path is provided and it's different from the current one,
            # update the path and re-read the file
            cls._instance._overwrites_file_path = overwrites_file_path
            cls._instance._read_overwrites_file()
        return cls._instance

    def _read_overwrites_file(self) -> None:
        """Read the overwrites JSON file and cache the data.

        Raises:
            FileNotFoundError: If the overwrites file doesn't exist.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        try:
            with open(self._overwrites_file_path, "r") as f:
                data = json.load(f)
                self._runtime_overwrites = (
                    data.get("runtime", {})
                    .get("internalArguments", {})
                    .get("resourceOverwrites", {})
                )
        except FileNotFoundError:
            self._runtime_overwrites = {}

    def get_overwrite(
        self, resource_type: str, resource_name: str, folder_path: Optional[str] = None
    ) -> Optional[Tuple[str, str]]:
        """Get an overwrite value for a specific resource.

        Args:
            resource_type: The type of resource (e.g., 'process', 'asset').
            resource_name: The name of the resource.

        Returns:
            A tuple of (name, folder_path) if found, None otherwise.
        """
        if folder_path:
            key = f"{resource_type}.{resource_name}.{folder_path}"
        else:
            key = f"{resource_type}.{resource_name}"

        if key not in self._runtime_overwrites:
            return None

        overwrite = self._runtime_overwrites[key]
        return (
            overwrite.get("name", resource_name),
            overwrite.get("folderPath", ""),
        )

    def get_and_apply_overwrite(
        self, resource_type: str, resource_name: str, folder_path: Optional[str] = None
    ) -> Tuple[Any, Any]:
        """Get and apply overwrites for a resource, falling back to provided values if no overwrites exist.

        Args:
            resource_type: The type of resource (e.g., 'process', 'asset').
            resource_name: The name of the resource.
            folder_path: Optional folder path to use if no overwrite exists.

        Returns:
            A tuple of (name, folder_path) with overwritten values if available,
            otherwise the original values.
        """
        overwrite = self.get_overwrite(resource_type, resource_name, folder_path)
        if overwrite:
            resource_name, folder_path = overwrite
        return resource_name, folder_path or None


@contextmanager
def read_resource_overwrites(
    resource_type: str,
    resource_name: str,
    folder_path: Optional[str] = None,
    overwrites_file_path: Optional[Path] = None,
) -> Generator[Tuple[str, str], None, None]:
    """Context manager for reading and applying resource overwrites.

    Args:
        resource_type: The type of resource (e.g., 'process', 'asset').
        resource_name: The name of the resource.
        folder_path: Optional folder path to use if no overwrite exists.
        overwrites_file_path: Optional path to the overwrites JSON file.

    Yields:
        A tuple of (name, folder_path) with overwritten values if available,
        otherwise the original values.

    Example:
        ```python
        with read_resource_overwrites("asset", "MyAsset") as (name, folder_path):
            # Use name and folder_path here
            pass
        ```
    """
    manager = OverwritesManager(overwrites_file_path)
    try:
        yield manager.get_and_apply_overwrite(resource_type, resource_name, folder_path)
    finally:
        pass
