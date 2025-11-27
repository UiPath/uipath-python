import json
import os
import shutil

import click

from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()


def generate_script(target_directory):
    template_path = os.path.join(
        os.path.dirname(__file__), "_templates/main.py.template"
    )
    target_path = os.path.join(target_directory, "main.py")

    shutil.copyfile(template_path, target_path)


def generate_pyproject(target_directory, project_name):
    project_toml_path = os.path.join(target_directory, "pyproject.toml")
    toml_content = f"""[project]
name = "{project_name}"
version = "0.0.1"
description = "{project_name}"
authors = [{{ name = "John Doe", email = "john.doe@myemail.com" }}]
dependencies = [
    "uipath>=2.2.0, <2.3.0"
]
requires-python = ">=3.11"
"""

    with open(project_toml_path, "w") as f:
        f.write(toml_content)


def generate_uipath_json(target_directory):
    uipath_json_path = os.path.join(target_directory, "uipath.json")
    uipath_config = {"functions": {"main": "main.py:main"}}

    with open(uipath_json_path, "w") as f:
        json.dump(uipath_config, f, indent=2)


@click.command()
@click.argument("name", type=str, default="")
def new(name: str):
    """Generate a quick-start project."""
    directory = os.getcwd()

    if not name:
        console.error(
            "Please specify a name for your project:\n`uipath new hello-world`"
        )

    result = Middlewares.next("new", name)

    if result.error_message:
        console.error(
            result.error_message, include_traceback=result.should_include_stacktrace
        )

    if result.info_message:
        console.info(result.info_message)

    if not result.should_continue:
        return

    with console.spinner(f"Creating new project {name} in current directory ..."):
        generate_script(directory)
        console.success("Created 'main.py' file.")
        generate_pyproject(directory, name)
        console.success("Created 'pyproject.toml' file.")
        generate_uipath_json(directory)
        console.success("Created 'uipath.json' file.")
        init_command = """uipath init"""
        run_command = """uipath run main '{"message": "Hello World!"}'"""
        console.hint(f""" Initialize project: {click.style(init_command, fg="cyan")}""")
        console.hint(f"""Run project: {click.style(run_command, fg="cyan")}""")


if __name__ == "__main__":
    new()
