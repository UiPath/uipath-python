# type: ignore
import importlib.resources
import json
import logging
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
from ._utils._parse_ast import generate_bindings
from .middlewares import Middlewares
from .models.runtime_schema import Bindings, Entrypoint, RuntimeSchema

console = ConsoleLogger()
logger = logging.getLogger(__name__)

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
        console.success(f"Created '{relative_path}' file.")


def generate_agent_md_file(target_directory: str, file_name: str) -> None:
    """Generate an agent-specific file from the packaged resource.

    Args:
        target_directory: The directory where the file should be created.
        file_name: The name of the file should be created.
    """
    target_path = os.path.join(target_directory, file_name)

    if os.path.exists(target_path):
        logger.debug(f"File '{target_path}' already exists.")
        return

    try:
        source_path = importlib.resources.files("uipath._resources").joinpath(file_name)

        with importlib.resources.as_file(source_path) as s_path:
            shutil.copy(s_path, target_path)

    except Exception as e:
        console.warning(f"Could not create {file_name}: {e}")


def generate_agent_md_files(target_directory: str) -> None:
    """Generate an agent-specific file from the packaged resource.

    Args:
        target_directory: The directory where the files should be created.
    """
    agent_dir = os.path.join(target_directory, ".agent")
    os.makedirs(agent_dir, exist_ok=True)

    root_files = ["AGENTS.md", "CLAUDE.md"]

    agent_files = ["CLI_REFERENCE.md", "REQUIRED_STRUCTURE.md", "SDK_REFERENCE.md"]

    for file_name in root_files:
        generate_agent_md_file(target_directory, file_name)

    for file_name in agent_files:
        generate_agent_md_file(agent_dir, file_name)

    console.success(f"Created {click.style('AGENTS.md', fg='cyan')} file.")


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


def write_config_file(config_data: Dict[str, Any] | RuntimeSchema) -> None:
    existing_settings = get_existing_settings(CONFIG_PATH)
    if existing_settings is not None:
        config_data.settings = existing_settings

    with open(CONFIG_PATH, "w") as config_file:
        if isinstance(config_data, RuntimeSchema):
            json_object = config_data.model_dump(by_alias=True, exclude_unset=True)
        else:
            json_object = config_data
        json.dump(json_object, config_file, indent=4)

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

        generate_agent_md_files(current_directory)
        script_path = get_user_script(current_directory, entrypoint=entrypoint)

        if not script_path:
            return

        try:
            args = generate_args(script_path)

            relative_path = Path(script_path).relative_to(current_directory).as_posix()
            bindings = None
            if infer_bindings:
                try:
                    bindings = generate_bindings(script_path)
                except Exception as e:
                    console.warning(f"Warning: Could not generate bindings: {str(e)}")
            if bindings is None:
                bindings = Bindings(
                    version="2.0",
                    resources=[],
                )
            config_data = RuntimeSchema(
                entrypoints=[
                    Entrypoint(
                        file_path=relative_path,
                        unique_id=str(uuid.uuid4()),
                        type="agent",
                        input=args["input"],
                        output=args["output"],
                    )
                ],
                bindings=bindings,
            )

            config_path = write_config_file(config_data)
            console.success(f"Created '{config_path}' file.")
        except Exception as e:
            console.error(f"Error creating configuration file:\n {str(e)}")
