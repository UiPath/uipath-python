import json
from pathlib import Path

from ..._config import UiPathConfig
from ..models.runtime_schema import (
    Bindings,
    Entrypoints,
)


def write_bindings_file(bindings: Bindings) -> Path:
    """Write bindings to a JSON file.

    Args:
        bindings: The Bindings object to write to file

    Returns:
        str: The path to the written bindings file
    """
    bindings_file_path = UiPathConfig.bindings_file_path
    with open(bindings_file_path, "w") as bindings_file:
        json_object = bindings.model_dump(by_alias=True, exclude_unset=True)
        json.dump(json_object, bindings_file, indent=4)

    return bindings_file_path


def write_entry_points_file(entry_points: Entrypoints) -> Path:
    """Write entrypoints to a JSON file.

    Args:
        entry_points: The entrypoints list

    Returns:
        str: The path to the written entry_points file
    """
    json_object = {
        "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
        "$id": "entry-points.json",
        **entry_points.model_dump(by_alias=True, exclude_unset=True),
    }

    entry_points_file_path = UiPathConfig.entry_points_file_path
    with open(entry_points_file_path, "w") as entry_points_file:
        json.dump(json_object, entry_points_file, indent=4)

    return entry_points_file_path
