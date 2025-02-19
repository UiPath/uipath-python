# type: ignore
import os
import shutil
import traceback

import click

from .middlewares import Middlewares


def generate_script(target_directory):
    template_path = os.path.join(
        os.path.dirname(__file__), "templates/main.py.template"
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
    "uipath_sdk>=0.0.44"
]
requires-python = ">=3.9"
"""

    with open(project_toml_path, "w") as f:
        f.write(toml_content)


@click.command()
@click.argument("name", type=str, default="")
def new(name: str):
    directory = os.getcwd()

    if not name:
        raise click.UsageError(
            "Please specify a name for your project\n`uipath new hello-world`"
        )

    click.echo(f"Initializing project {name} in current directory..")

    result = Middlewares.next("new", name)

    if result.error_message:
        click.echo(result.error_message)
        if result.should_include_stacktrace:
            click.echo(traceback.format_exc())
        click.get_current_context().exit(1)

    if result.info_message:
        click.echo(result.info_message)

    if not result.should_continue:
        return

    generate_script(directory)
    click.echo("Created main.py file.")
    generate_pyproject(directory, name)
    click.echo("Created pyproject.toml file.")

    ctx = click.get_current_context()
    init_cmd = ctx.parent.command.get_command(ctx, "init")
    ctx.invoke(init_cmd)

    click.echo("""` uipath run main.py '{"message": "Hello World!"}' `""")


if __name__ == "__main__":
    new()
