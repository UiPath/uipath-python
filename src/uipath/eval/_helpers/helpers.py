import json
import os

import click

from uipath._cli._utils._console import ConsoleLogger
from uipath._utils.constants import UIPATH_CONFIG_FILE


def auto_discover_entrypoint() -> str:
    """Auto-discover entrypoint from config file.

    Returns:
        Path to the entrypoint

    Raises:
        ValueError: If no entrypoint found or multiple entrypoints exist
    """
    console = ConsoleLogger()

    if not os.path.isfile(UIPATH_CONFIG_FILE):
        raise ValueError(
            f"File '{UIPATH_CONFIG_FILE}' not found. Please run 'uipath init'."
        )

    with open(UIPATH_CONFIG_FILE, "r", encoding="utf-8") as f:
        uipath_config = json.loads(f.read())

    entrypoints = uipath_config.get("entryPoints", [])

    if not entrypoints:
        raise ValueError(
            f"No entrypoints found in {UIPATH_CONFIG_FILE}. Please run 'uipath init'."
        )

    if len(entrypoints) > 1:
        entrypoint_paths = [ep.get("filePath") for ep in entrypoints]
        raise ValueError(
            f"Multiple entrypoints found: {entrypoint_paths}. "
            f"Please specify which entrypoint to use."
        )

    entrypoint = entrypoints[0].get("filePath")
    console.info(
        f"Auto-discovered agent entrypoint: {click.style(entrypoint, fg='cyan')}"
    )
    return entrypoint
