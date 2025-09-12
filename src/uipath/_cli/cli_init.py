# type: ignore
import importlib.resources
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import click

from .._utils.constants import ENV_TELEMETRY_ENABLED
from ..telemetry import track
from ..telemetry._constants import _PROJECT_KEY, _TELEMETRY_CONFIG_FILE
from ._utils._console import ConsoleLogger
from ._utils._input_args import generate_args
from ._utils._parse_ast import generate_bindings_json
from .middlewares import Middlewares

console = ConsoleLogger()

CONFIG_PATH = "uipath.json"


def create_telemetry_config_file(target_directory: str) -> None:
    """Create telemetry file if telemetry is enabled.

    Args:
        target_directory: The directory where the .uipath folder should be created.
    """
    telemetry_enabled = os.getenv(ENV_TELEMETRY_ENABLED, "true").lower() == "true"

    if not telemetry_enabled:
        return

    uipath_dir = os.path.join(target_directory, ".uipath")
    telemetry_file = os.path.join(uipath_dir, _TELEMETRY_CONFIG_FILE)

    if os.path.exists(telemetry_file):
        return

    os.makedirs(uipath_dir, exist_ok=True)
    telemetry_data = {
        _PROJECT_KEY: os.getenv("UIPATH_PROJECT_ID", None) or str(uuid.uuid4())
    }

    with open(telemetry_file, "w") as f:
        json.dump(telemetry_data, f, indent=4)


def generate_env_file(target_directory):
    env_path = os.path.join(target_directory, ".env")

    if not os.path.exists(env_path):
        relative_path = os.path.relpath(env_path, target_directory)
        with open(env_path, "w"):
            pass
        console.success(f" Created '{relative_path}' file.")


def generate_agents_md(target_directory: str) -> None:
    """Generate AGENTS.md file from the packaged resource.

    Args:
        target_directory: The directory where AGENTS.md should be created.
    """
    target_path = os.path.join(target_directory, "AGENTS.md")

    # Skip if file already exists
    if os.path.exists(target_path):
        console.info("Skipping 'AGENTS.md' creation as it already exists.")
        return

    try:
        # Get the resource path using importlib.resources
        source_path = importlib.resources.files("uipath._resources").joinpath(
            "AGENTS.md"
        )

        # Copy the file to the target directory
        with importlib.resources.as_file(source_path) as s_path:
            shutil.copy(s_path, target_path)

        console.success(" Created 'AGENTS.md' file.")
    except Exception as e:
        console.warning(f"Could not create AGENTS.md: {e}")


def get_existing_settings(config_path: str) -> Optional[Dict[str, Any]]:
    """Read existing settings from uipath.json if it exists.

    Args:
        config_path: Path to the uipath.json file.

    Returns:
        The settings dictionary if it exists, None otherwise.
    """
    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, "r") as config_file:
            existing_config = json.load(config_file)
            return existing_config.get("settings")
    except (json.JSONDecodeError, IOError):
        return None


def get_user_script(directory: str, entrypoint: Optional[str] = None) -> Optional[str]:
    """Find the Python script to process."""
    if entrypoint:
        script_path = os.path.join(directory, entrypoint)
        if not os.path.isfile(script_path):
            console.error(
                f"The {entrypoint} file does not exist in the current directory."
            )
            return None
        return script_path

    python_files = [f for f in os.listdir(directory) if f.endswith(".py")]

    if not python_files:
        console.error(
            "No python files found in the current directory.\nPlease specify the entrypoint: `uipath init <entrypoint_path>`"
        )
        return None
    elif len(python_files) == 1:
        return os.path.join(directory, python_files[0])
    else:
        console.error(
            "Multiple python files found in the current directory.\nPlease specify the entrypoint: `uipath init <entrypoint_path>`"
        )
        return None


def write_config_file(config_data: Dict[str, Any]) -> None:
    existing_settings = get_existing_settings(CONFIG_PATH)
    if existing_settings is not None:
        config_data["settings"] = existing_settings

    with open(CONFIG_PATH, "w") as config_file:
        json.dump(config_data, config_file, indent=4)

    return CONFIG_PATH


@click.command()
@click.argument("entrypoint", required=False, default=None)
@click.option(
    "--infer-bindings/--no-infer-bindings",
    is_flag=True,
    required=False,
    default=True,
    help="Infer bindings from the script.",
)
@track
def init(entrypoint: str, infer_bindings: bool) -> None:
    """Create uipath.json with input/output schemas and bindings."""
    with console.spinner("Initializing UiPath project ..."):
        current_directory = os.getcwd()
        generate_env_file(current_directory)
        create_telemetry_config_file(current_directory)
        generate_agents_md(current_directory)

        result = Middlewares.next(
            "init",
            entrypoint,
            options={"infer_bindings": infer_bindings},
            write_config=write_config_file,
        )

        if result.error_message:
            console.error(
                result.error_message, include_traceback=result.should_include_stacktrace
            )

        if result.info_message:
            console.info(result.info_message)

        if not result.should_continue:
            return

        script_path = get_user_script(current_directory, entrypoint=entrypoint)

        if not script_path:
            return

        try:
            args = generate_args(script_path)

            relative_path = Path(script_path).relative_to(current_directory).as_posix()

            config_data = {
                "entryPoints": [
                    {
                        "filePath": relative_path,
                        "uniqueId": str(uuid.uuid4()),
                        # "type": "process", OR BE doesn't offer json schema support for type: Process
                        "type": "agent",
                        "input": args["input"],
                        "output": args["output"],
                    }
                ]
            }

            # Generate bindings JSON based on the script path
            try:
                if infer_bindings:
                    bindings_data = generate_bindings_json(script_path)
                else:
                    bindings_data = {}
                # Add bindings to the config data
                config_data["bindings"] = bindings_data
            except Exception as e:
                console.warning(f"Warning: Could not generate bindings: {str(e)}")

            config_path = write_config_file(config_data)
            console.success(f"Created '{config_path}' file.")
        except Exception as e:
            console.error(f"Error creating configuration file:\n {str(e)}")
