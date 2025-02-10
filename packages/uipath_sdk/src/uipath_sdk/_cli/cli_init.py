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
        f.write("uipath_sdk\n")
        f.write("langgraph\n")
        f.write("langgraph-sdk\n")
        f.write("ipython\n")


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


def generateEnvFile(target_directory, project_name):
    final_path = get_final_path(target_directory, project_name)

    env_path = os.path.join(final_path, ".env")
    with open(env_path, "w") as f:
        f.write("UIPATH_TOKEN=YOUR_TOKEN_HERE\n")
        f.write("UIPATH_BASE_URL=alpha.uipath.com\n")
        f.write("UIPATH_ACCOUNT_NAME=\n")
        f.write("UIPATH_TENANT_NAME=\n")
        f.write("UIPATH_FOLDER_PATH=\n")

    print(f"Created .env file at {env_path}")
    print("Please fill in the .env file with your UiPath credentials")


@click.command()
@click.argument("name", type=str, default="my-agent")
@click.argument("directory", type=str, default="./")
@click.argument("description", type=str, default="my-agent description")
def init(name, directory, description):
    type = "agent"
    click.echo(
        f"Initializing project {name} with description {description} in directory {directory}"
    )
    generateInitFile(directory, name)
    generateRequirementsFile(directory, name)
    generateEnvFile(directory, name)
    generateConfigFile(directory, name, description, type)
    click.echo(
        f"Make sure to run `pip install -r {os.path.join(directory, 'requirements.txt')}` to install dependencies"
    )
