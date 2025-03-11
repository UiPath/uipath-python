# type: ignore
import json
import os
import traceback
import uuid
from typing import Optional

import click

from .input_args import generate_args
from .middlewares import Middlewares
from .parse_ast import generate_bindings_json


def generate_env_file(target_directory):
    env_path = os.path.join(target_directory, ".env")

    if not os.path.exists(env_path):
        relative_path = os.path.relpath(env_path, target_directory)
        click.echo(f"Created {relative_path} file.")
        with open(env_path, "w") as f:
            f.write("UIPATH_ACCESS_TOKEN=YOUR_TOKEN_HERE\n")
            f.write("UIPATH_URL=https://alpha.uipath.com/ACCOUNT_NAME/TENANT_NAME\n")


def get_user_script(directory: str, entrypoint: Optional[str] = None) -> Optional[str]:
    """Find the Python script to process."""
    if entrypoint:
        script_path = os.path.join(directory, entrypoint)
        if not os.path.isfile(script_path):
            click.echo(f"The {entrypoint} file does not exist in the current directory")
            return None
        return script_path

    python_files = [f for f in os.listdir(directory) if f.endswith(".py")]

    if not python_files:
        click.echo("No Python files found in the directory")
        return None
    elif len(python_files) == 1:
        return os.path.join(directory, python_files[0])
    else:
        click.echo(
            "Multiple Python files found in the current directory.\nPlease specify the entrypoint: `uipath init <entrypoint_path>`"
        )
        return None


@click.command()
@click.argument("entrypoint", required=False, default=None)
def init(entrypoint: str) -> None:
    """Initialize a uipath.json configuration file for the script."""
    current_directory = os.getcwd()
    generate_env_file(current_directory)

    result = Middlewares.next("init", entrypoint)

    if result.error_message:
        click.echo(result.error_message)
        if result.should_include_stacktrace:
            click.echo(traceback.format_exc())
        click.get_current_context().exit(1)

    if result.info_message:
        click.echo(result.info_message)

    if not result.should_continue:
        return

    script_path = get_user_script(current_directory, entrypoint=entrypoint)

    if not script_path:
        click.get_current_context().exit(1)

    try:
        args = generate_args(script_path)

        relative_path = os.path.relpath(script_path, current_directory)

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

            click.echo("Bindings generated successfully.")
        except Exception as e:
            click.echo(f"Warning: Could not generate bindings: {str(e)}")

        config_path = "uipath.json"
        with open(config_path, "w") as config_file:
            json.dump(config_data, config_file, indent=4)

        click.echo(f"Configuration file {config_path} created successfully.")

    except Exception as e:
        click.echo(f"Error generating configuration: {str(e)}")
        click.echo(traceback.format_exc())
        click.get_current_context().exit(1)
