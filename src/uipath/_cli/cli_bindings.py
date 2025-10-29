# type: ignore
import json
import logging
import os
from typing import Any, Dict, Optional

import click

from ..telemetry import track
from ._utils._console import ConsoleLogger

console = ConsoleLogger()
logger = logging.getLogger(__name__)

CONFIG_PATH = "uipath.json"


def load_config() -> Dict[str, Any]:
    """Load the uipath.json configuration file.

    Returns:
        The configuration dictionary.

    Raises:
        FileNotFoundError: If uipath.json doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"'{CONFIG_PATH}' not found. Please run 'uipath init' first."
        )

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(config: Dict[str, Any]) -> None:
    """Save the configuration to uipath.json.

    Args:
        config: The configuration dictionary to save.
    """
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


def get_or_create_runtime_overwrites(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get or create the runtime.internalArguments.resourceOverwrites section.

    Args:
        config: The configuration dictionary.

    Returns:
        The resourceOverwrites dictionary.
    """
    if "runtime" not in config:
        config["runtime"] = {}

    if "internalArguments" not in config["runtime"]:
        config["runtime"]["internalArguments"] = {}

    if "resourceOverwrites" not in config["runtime"]["internalArguments"]:
        config["runtime"]["internalArguments"]["resourceOverwrites"] = {}

    return config["runtime"]["internalArguments"]["resourceOverwrites"]


@click.group()
def bindings() -> None:
    """Manage bindings for UiPath resources (assets, processes, queues, etc.)."""
    pass


@bindings.command(name="create")
@click.argument("binding_key", required=True)
@click.option(
    "--resource-type",
    "-t",
    required=True,
    type=click.Choice(["asset", "process", "queue"], case_sensitive=False),
    help="The type of resource (asset, process, queue)",
)
@click.option(
    "--name",
    "-n",
    required=True,
    help="The actual resource name in Orchestrator",
)
@click.option(
    "--folder-path",
    "-f",
    required=False,
    default=None,
    help="The folder path where the resource is located",
)
@track
def create(
    binding_key: str, resource_type: str, name: str, folder_path: Optional[str]
) -> None:
    """Create a new binding for a UiPath resource.

    BINDING_KEY is the identifier you'll use in your code (e.g., 'my-asset').

    Examples:

        Create an asset binding:

            uipath bindings create my-asset -t asset -n "MyActualAssetName"

        Create a process binding with folder:

            uipath bindings create my-process -t process -n "MyProcess" -f "/Shared/Production"
    """
    try:
        config = load_config()
        overwrites = get_or_create_runtime_overwrites(config)

        # Create the binding key with resource type
        full_key = f"{resource_type}.{binding_key}"

        # Check if binding already exists
        if full_key in overwrites:
            console.warning(
                f"Binding '{binding_key}' already exists for resource type '{resource_type}'. Updating..."
            )

        # Create the binding
        binding_data = {"name": name}
        if folder_path:
            binding_data["folderPath"] = folder_path

        overwrites[full_key] = binding_data

        # Save the config
        save_config(config)

        console.success(
            f"Created binding '{binding_key}' -> {resource_type} '{name}'"
            + (f" in folder '{folder_path}'" if folder_path else "")
        )

    except FileNotFoundError as e:
        console.error(str(e))
    except Exception as e:
        console.error(f"Error creating binding: {str(e)}")


@bindings.command(name="list")
@track
def list_bindings() -> None:
    """List all configured bindings."""
    try:
        config = load_config()
        overwrites = config.get("runtime", {}).get("internalArguments", {}).get(
            "resourceOverwrites", {}
        )

        if not overwrites:
            console.info("No bindings configured.")
            return

        console.info("Configured bindings:\n")
        for key, value in overwrites.items():
            parts = key.split(".", 1)
            if len(parts) == 2:
                resource_type, binding_key = parts
                name = value.get("name", "N/A")
                folder_path = value.get("folderPath", "")
                folder_info = f" (folder: {folder_path})" if folder_path else ""
                click.echo(
                    f"  {click.style(binding_key, fg='cyan')} [{resource_type}] -> {name}{folder_info}"
                )

    except FileNotFoundError as e:
        console.error(str(e))
    except Exception as e:
        console.error(f"Error listing bindings: {str(e)}")


@bindings.command(name="remove")
@click.argument("binding_key", required=True)
@click.option(
    "--resource-type",
    "-t",
    required=True,
    type=click.Choice(["asset", "process", "queue"], case_sensitive=False),
    help="The type of resource (asset, process, queue)",
)
@track
def remove(binding_key: str, resource_type: str) -> None:
    """Remove a binding.

    BINDING_KEY is the identifier used in your code.

    Examples:

        uipath bindings remove my-asset -t asset
    """
    try:
        config = load_config()
        overwrites = config.get("runtime", {}).get("internalArguments", {}).get(
            "resourceOverwrites", {}
        )

        full_key = f"{resource_type}.{binding_key}"

        if full_key not in overwrites:
            console.error(
                f"Binding '{binding_key}' for resource type '{resource_type}' not found."
            )
            return

        del overwrites[full_key]
        save_config(config)

        console.success(
            f"Removed binding '{binding_key}' for resource type '{resource_type}'"
        )

    except FileNotFoundError as e:
        console.error(str(e))
    except Exception as e:
        console.error(f"Error removing binding: {str(e)}")
