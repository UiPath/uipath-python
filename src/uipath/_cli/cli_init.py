# type: ignore
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import click

from ._utils._console import ConsoleLogger
from ._utils._input_args import generate_args
from ._utils._parse_ast import generate_bindings_json
from .middlewares import Middlewares

console = ConsoleLogger()


def generate_env_file(target_directory):
    env_path = os.path.join(target_directory, ".env")

    if not os.path.exists(env_path):
        relative_path = os.path.relpath(env_path, target_directory)
        with open(env_path, "w"):
            pass
        console.success(f" Created '{relative_path}' file.")


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
        console.error("No python files found in the current directory.")
        return None
    elif len(python_files) == 1:
        return os.path.join(directory, python_files[0])
    else:
        console.error(
            "Multiple python files found in the current directory.\nPlease specify the entrypoint: `uipath init <entrypoint_path>`"
        )
        return None


@click.command()
@click.argument("entrypoint", required=False, default=None)
def init(entrypoint: str) -> None:
    """Create uipath.json with input/output schemas and bindings."""
    with console.spinner("Initializing UiPath project ..."):
        current_directory = os.getcwd()
        generate_env_file(current_directory)

        result = Middlewares.next("init", entrypoint)

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
                bindings_data = generate_bindings_json(script_path)
                # Add bindings to the config data
                config_data["bindings"] = bindings_data
            except Exception as e:
                console.warning(f"Warning: Could not generate bindings: {str(e)}")

            config_path = "uipath.json"
            with open(config_path, "w") as config_file:
                json.dump(config_data, config_file, indent=4)

            console.success(f"Created '{config_path}' file.")
        except Exception as e:
            console.error(f"Error creating configuration file:\n {str(e)}")
