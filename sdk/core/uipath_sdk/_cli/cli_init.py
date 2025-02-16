# type: ignore
import json
import os
import uuid
from typing import Optional

import click

from .input_args import generate_args
from .middlewares import Middlewares


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
            "Multiple Python files in current directory\nPlease specify the entrypoint: `uipath init <file>`"
        )
        return None


@click.command()
@click.argument("entrypoint", required=False, default=None)
def init(entrypoint: str) -> None:
    """Initialize a uipath.json configuration file for the script."""
    should_continue, errorMessage = Middlewares.next("init", entrypoint)

    if errorMessage:
        click.echo(f"{errorMessage}")

    if not should_continue:
        return

    current_directory = os.getcwd()
    script_path = get_user_script(current_directory, entrypoint=entrypoint)

    if not script_path:
        return

    try:
        args = generate_args(script_path)

        relative_path = os.path.relpath(script_path, current_directory)

        config_data = {
            "entryPoints": [
                {
                    "filePath": relative_path,
                    "unique_id": str(uuid.uuid4()),
                    "type": "process",
                    "input": args["input"],
                    "output": args["output"],
                }
            ]
        }

        config_path = "uipath.json"
        with open(config_path, "w") as config_file:
            json.dump(config_data, config_file, indent=4)

        click.echo(f"Created configuration file at {config_path}")

    except Exception as e:
        click.echo(f"Error generating configuration: {str(e)}")
