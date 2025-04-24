# type: ignore
import json
import logging
import os
import traceback
import uuid
from pathlib import Path
from typing import Optional

import click

from .._utils._logs import setup_logging
from ._utils._input_args import generate_args
from ._utils._parse_ast import generate_bindings_json
from .middlewares import Middlewares

logger = logging.getLogger(__name__)


def generate_env_file(target_directory):
    env_path = os.path.join(target_directory, ".env")
    logger.debug(f"Checking for .env file at: {env_path}")

    if not os.path.exists(env_path):
        relative_path = os.path.relpath(env_path, target_directory)
        logger.info(f"Creating {relative_path} file")
        with open(env_path, "w") as f:
            f.write("UIPATH_ACCESS_TOKEN=YOUR_TOKEN_HERE\n")
            f.write("UIPATH_URL=https://cloud.uipath.com/ACCOUNT_NAME/TENANT_NAME\n")
        logger.debug("Created .env file with default values")


def get_user_script(directory: str, entrypoint: Optional[str] = None) -> Optional[str]:
    """Find the Python script to process."""
    logger.debug(f"Looking for script in directory: {directory}")

    if entrypoint:
        script_path = os.path.join(directory, entrypoint)
        logger.debug(f"Checking specified entrypoint: {script_path}")
        if not os.path.isfile(script_path):
            logger.error(
                f"The {entrypoint} file does not exist in the current directory"
            )
            return None
        return script_path

    python_files = [f for f in os.listdir(directory) if f.endswith(".py")]
    logger.debug(f"Found Python files: {python_files}")

    if not python_files:
        logger.error("No Python files found in the directory")
        return None
    elif len(python_files) == 1:
        script_path = os.path.join(directory, python_files[0])
        logger.debug(f"Using single Python file found: {script_path}")
        return script_path
    else:
        logger.warning("Multiple Python files found in the current directory")
        logger.info("Please specify the entrypoint: `uipath init <entrypoint_path>`")
        return None


@click.command()
@click.argument("entrypoint", required=False, default=None)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def init(entrypoint: str, verbose: bool) -> None:
    """Initialize a uipath.json configuration file for the script."""
    # Setup logging based on verbose flag
    setup_logging(should_debug=verbose)

    logger.debug(f"Starting init command with entrypoint: {entrypoint}")
    current_directory = os.getcwd()
    logger.debug(f"Current working directory: {current_directory}")

    generate_env_file(current_directory)

    logger.debug("Running init middlewares")
    result = Middlewares.next("init", entrypoint)

    if result.error_message:
        logger.error(result.error_message)
        if result.should_include_stacktrace:
            logger.error(traceback.format_exc())
        click.get_current_context().exit(1)

    if result.info_message:
        logger.info(result.info_message)

    if not result.should_continue:
        logger.debug("Middleware chain stopped execution")
        return

    script_path = get_user_script(current_directory, entrypoint=entrypoint)

    if not script_path:
        logger.error("No valid script found")
        click.get_current_context().exit(1)

    try:
        logger.debug(f"Generating args for script: {script_path}")
        args = generate_args(script_path)

        relative_path = Path(script_path).relative_to(current_directory).as_posix()
        logger.debug(f"Relative path to script: {relative_path}")

        config_data = {
            "entryPoints": [
                {
                    "filePath": relative_path,
                    "uniqueId": str(uuid.uuid4()),
                    "type": "agent",
                    "input": args["input"],
                    "output": args["output"],
                }
            ]
        }
        logger.debug("Created base config data")

        # Generate bindings JSON based on the script path
        try:
            logger.debug("Generating bindings JSON")
            bindings_data = generate_bindings_json(script_path)

            # Add bindings to the config data
            config_data["bindings"] = bindings_data
            logger.info("Bindings generated successfully")
        except Exception as e:
            logger.warning(f"Could not generate bindings: {str(e)}")

        config_path = "uipath.json"
        logger.debug(f"Writing config to: {config_path}")
        with open(config_path, "w") as config_file:
            json.dump(config_data, config_file, indent=4)

        logger.info(f"Configuration file {config_path} created successfully")

    except Exception as e:
        logger.error(f"Error generating configuration: {str(e)}")
        logger.error(traceback.format_exc())
        click.get_current_context().exit(1)
