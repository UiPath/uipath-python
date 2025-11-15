# type: ignore
import asyncio
import importlib.resources
import json
import logging
import os
import shutil
import uuid
from typing import Any, Dict, Optional

import click

from .._config import UiPathConfig
from .._utils.constants import ENV_TELEMETRY_ENABLED
from ..telemetry._constants import _PROJECT_KEY, _TELEMETRY_CONFIG_FILE
from ._runtime._runtime import get_user_script
from ._runtime._runtime_factory import generate_runtime_factory
from ._utils._console import ConsoleLogger
from ._utils._parse_ast import write_bindings_file, write_entry_points_file
from .middlewares import Middlewares
from .models.runtime_schema import Entrypoints, RuntimeSchema

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
    telemetry_data = {_PROJECT_KEY: UiPathConfig.project_id or str(uuid.uuid4())}

    with open(telemetry_file, "w") as f:
        json.dump(telemetry_data, f, indent=4)


def generate_env_file(target_directory):
    env_path = os.path.join(target_directory, ".env")

    if not os.path.exists(env_path):
        relative_path = os.path.relpath(env_path, target_directory)
        with open(env_path, "w"):
            pass
        console.success(f"Created '{relative_path}' file.")


def generate_agent_md_file(
    target_directory: str, file_name: str, no_agents_md_override: bool
) -> bool:
    """Generate an agent-specific file from the packaged resource.

    Args:
        target_directory: The directory where the file should be created.
        file_name: The name of the file should be created.
        no_agents_md_override: Whether to override existing files.
    """
    target_path = os.path.join(target_directory, file_name)

    will_override = os.path.exists(target_path)

    if will_override and no_agents_md_override:
        console.success(
            f"File {click.style(target_path, fg='cyan')} already exists. Skipping."
        )
        return False

    try:
        source_path = importlib.resources.files("uipath._resources").joinpath(file_name)

        with importlib.resources.as_file(source_path) as s_path:
            shutil.copy(s_path, target_path)

        if will_override:
            logger.debug(f"File '{target_path}' has been overridden.")

        return will_override

    except Exception as e:
        console.warning(f"Could not create {file_name}: {e}")

    return False


def generate_agent_md_files(target_directory: str, no_agents_md_override: bool) -> None:
    """Generate an agent-specific file from the packaged resource.

    Args:
        target_directory: The directory where the files should be created.
        no_agents_md_override: Whether to override existing files.
    """
    agent_dir = os.path.join(target_directory, ".agent")
    os.makedirs(agent_dir, exist_ok=True)

    root_files = ["AGENTS.md", "CLAUDE.md"]

    agent_files = ["CLI_REFERENCE.md", "REQUIRED_STRUCTURE.md", "SDK_REFERENCE.md"]

    any_overridden = False

    for file_name in root_files:
        if generate_agent_md_file(target_directory, file_name, no_agents_md_override):
            any_overridden = True

    for file_name in agent_files:
        if generate_agent_md_file(agent_dir, file_name, no_agents_md_override):
            any_overridden = True

    if any_overridden:
        console.success(f"Updated {click.style('AGENTS.md', fg='cyan')} related files.")
        return

    console.success(f"Created {click.style('AGENTS.md', fg='cyan')} related files.")


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
@click.option(
    "--no-agents-md-override",
    is_flag=True,
    required=False,
    default=False,
    help="Won't override existing .agent files and AGENTS.md file.",
)
def init(entrypoint: str, infer_bindings: bool, no_agents_md_override: bool) -> None:
    """Create uipath.json with input/output schemas and bindings."""
    with console.spinner("Initializing UiPath project ..."):
        current_directory = os.getcwd()
        generate_env_file(current_directory)
        create_telemetry_config_file(current_directory)

        result = Middlewares.next(
            "init",
            entrypoint,
            options={
                "infer_bindings": infer_bindings,
                "no_agents_md_override": no_agents_md_override,
            },
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

        generate_agent_md_files(current_directory, no_agents_md_override)
        script_path = get_user_script(current_directory, entrypoint=entrypoint)
        if not script_path:
            return

        context_args = {
            "runtime_dir": os.getcwd(),
            "entrypoint": script_path,
        }

        async def initialize() -> None:
            try:
                runtime = generate_runtime_factory().new_runtime(**context_args)

                config_path = write_config_file(
                    RuntimeSchema(
                        # settings={"isConversational": False}
                    )
                )
                console.success(f"Created '{config_path}' file.")

                bindings_path = write_bindings_file(await runtime.get_bindings())
                console.success(f"Created '{bindings_path}' file.")
                entry_point = await runtime.get_entrypoint()
                entry_points_path = write_entry_points_file(
                    Entrypoints(entry_points=[entry_point])
                )
                console.success(f"Created '{entry_points_path}' file.")

            except Exception as e:
                console.error(f"Error creating configuration file:\n {str(e)}")

        asyncio.run(initialize())
