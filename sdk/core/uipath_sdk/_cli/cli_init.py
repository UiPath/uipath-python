# type: ignore
import json
import os

import click

from .middlewares import Middlewares
from .input_args import generate_args

def get_user_script(directory, entrypoint=None):
    if entrypoint:
        script_path = os.path.join(directory, entrypoint)
        if not os.path.isfile(script_path):
            raise Exception(f"{entrypoint} file does not exist in the directory")
    else:
        python_files = [f for f in os.listdir(directory) if f.endswith('.py')]

        if not python_files:
            raise Exception("No Python files found in the directory")
        elif len(python_files) == 1:
            script_path = os.path.join(directory, python_files[0])
        else:
            raise Exception("Multiple Python files in current directory\nPlease specify the entrypoint: uipath init <entrypoint>")

    return script_path

@click.command()
@click.argument("entrypoint", required=False, default=None)
def init(entrypoint: str):
    should_continue, errorMessage = Middlewares.next("init", entrypoint)

    if errorMessage:
        click.echo(f"{errorMessage}")

    if not should_continue:
        return

    current_directory = os.getcwd()
    script_name = get_user_script(current_directory, entrypoint=entrypoint)
    script_path = os.path.join(current_directory, script_name)

    args = generate_args(script_path)

    relative_path = os.path.relpath(script_name, current_directory)

    config_path = "uipath.json"
    config_data = {
        "entryPoints": [
            {
                "filePath": relative_path,
                "type": "process",
                "input": args["input"],
                "output": args["output"]
            }
        ]
    }

    with open(config_path, "w") as config_file:
        json.dump(config_data, config_file, indent=4)

    click.echo(f"Created configuration file at {config_path}")
