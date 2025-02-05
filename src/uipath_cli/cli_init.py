# type: ignore
import json
import os
import shutil

import click


def get_final_path(target_directory, project_name):
    final_path = os.path.abspath(target_directory)
    if not os.path.isdir(final_path):
        raise Exception("Target directory does not exist")
    elif os.listdir(final_path):
        final_path = os.path.join(final_path, project_name)

    if not os.path.isdir(final_path):
        os.mkdir(final_path)

    return final_path


def generateInitFile(target_directory, project_name):
    final_path = get_final_path(target_directory, project_name)

    template_path = os.path.join(
        os.path.dirname(__file__), "templates/main.py.template"
    )
    target_path = os.path.join(final_path, "main.py")

    shutil.copyfile(template_path, target_path)


def generateRequirementsFile(target_directory, project_name):
    final_path = get_final_path(target_directory, project_name)

    requirements_path = os.path.join(final_path, "requirements.txt")
    with open(requirements_path, "w") as f:
        f.write("uipath==1.0.1\n")


def generateConfigFile(target_directory, project_name, description, type):
    final_path = get_final_path(target_directory, project_name)

    config_path = os.path.join(final_path, "config.json")
    config_data = {
        "project_name": project_name,
        "description": description,
        "type": type,
    }

    with open(config_path, "w") as config_file:
        json.dump(config_data, config_file, indent=4)


@click.command()
@click.option(
    "--name", prompt="Name", default="my-first-project", help="Name of your project"
)
@click.option(
    "--type",
    prompt="Type (process/agent)",
    help="Whether the project is a process or an agent",
)
@click.option(
    "--description",
    prompt="Description",
    default="",
    help="Description for your project",
)
@click.option(
    "--directory",
    prompt="Target Directory",
    default="./proj",
    help="Target directory for your project",
)
def cli_init(name, description, directory, type):
    click.echo(
        f"Initializing project {name} with description {description} in directory {directory}"
    )
    generateInitFile(directory, name)
    generateRequirementsFile(directory, name)
    generateConfigFile(directory, name, description, type)
    click.echo(
        f"Make sure to run `pip install -r {os.path.join(directory, 'requirements.txt')}` to install dependencies"
    )
