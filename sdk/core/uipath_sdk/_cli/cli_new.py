# type: ignore
import json
import os
import shutil

import click

try:
    import tomllib
except ImportError:
    import tomli as tomllib

langchain_init = None
try:
    from uipath_langchain import init as langchain_init
except ImportError:
    pass


def get_final_path(target_directory, project_name):
    final_path = os.path.abspath(target_directory)
    if not os.path.isdir(final_path):
        raise Exception("Target directory does not exist")
    elif os.listdir(final_path):
        final_path = os.path.join(final_path, project_name)

    if not os.path.isdir(final_path):
        os.mkdir(final_path)

    return final_path


def generate_init_file(target_directory):
    template_path = os.path.join(
        os.path.dirname(__file__), "templates/main.py.template"
    )
    target_path = os.path.join(target_directory, "main.py")

    shutil.copyfile(template_path, target_path)


def generate_requirements_file(target_directory):
    requirements_path = os.path.join(target_directory, "requirements.txt")
    with open(requirements_path, "w") as f:
        f.write("uipath_sdk\n")


def generate_project_toml_file(target_directory, project_name, description, authors):
    project_toml_path = os.path.join(target_directory, "pyproject.toml")
    toml_content = f"""[project]
name = "{project_name}"
description = "{description}"
version = "0.0.1"
authors = [{{ name = "{authors}" }}]
"""
    with open(project_toml_path, "w") as f:
        f.write(toml_content)


def generate_config_file(final_path, project_name, description, type, authors):
    config_path = os.path.join(final_path, "config.json")
    config_data = {
        # "project_name": project_name,
        # "description": description,
        "type": type,
        # "authors": authors,
    }

    with open(config_path, "w") as config_file:
        json.dump(config_data, config_file, indent=4)


def generate_seed_env_file(target_directory):
    env_path = os.path.join(target_directory, ".env")

    if os.path.exists(env_path):
        # Read existing env file
        with open(env_path, "r") as f:
            existing_env = f.read()

        # Check which variables need to be added
        env_vars = {
            "UIPATH_ACCESS_TOKEN": "YOUR_TOKEN_HERE",
            "UIPATH_URL": "alpha.uipath.com",
        }

        # Only append missing variables
        with open(env_path, "a") as f:
            for key, value in env_vars.items():
                if key not in existing_env:
                    f.write(f"{key}={value}\n")
        return

    click.echo(f"Created .env file at {env_path}")
    with open(env_path, "w") as f:
        f.write("UIPATH_ACCESS_TOKEN=YOUR_TOKEN_HERE\n")
        f.write("UIPATH_URL=alpha.uipath.com/ACCOUNT_NAME/TENANT_NAME/orchestrator_\n")


def has_toml_file(directory: str) -> bool:
    return os.path.exists(os.path.join(directory, "pyproject.toml"))


def read_toml_file(file_path: str) -> dict[str, any]:
    with open(file_path, "rb") as f:
        content = tomllib.load(f)
        return {
            "name": content["project"]["name"],
            "description": content["project"]["description"],
            # "version": content["project"]["version"],
            "authors": content["project"].get("authors", [{"name": ""}])[0]["name"],
        }


def check_uipath_project_already_initialized(directory: str) -> bool:
    return os.path.exists(os.path.join(directory, ".uipath")) and os.path.exists(
        os.path.join(directory, ".uipath/config.json")
    )


def configure_existing_project(
    directory: str,
    override_name: str = None,
    override_description: str = None,
    override_authors: str = None,
):
    if check_uipath_project_already_initialized(directory):
        click.echo("Project already initialized")
        return

    uipath_dir = os.path.join(directory, ".uipath")
    if not os.path.exists(uipath_dir):
        os.makedirs(uipath_dir)
        click.echo(f"Created .uipath directory at {uipath_dir}")

    project_data = read_toml_file(os.path.join(directory, "pyproject.toml"))
    generate_config_file(
        f"{directory}/.uipath",
        override_name if override_name else project_data["name"],
        override_description if override_description else project_data["description"],
        "agent",
        override_authors if override_authors else project_data["authors"],
    )

    generate_seed_env_file(f"{directory}")


@click.command()
@click.argument("directory", type=str, default=os.getcwd())
@click.argument("name", type=str, default="")
@click.argument("description", type=str, default="")
@click.argument("authors", type=str, default="")
def new(name, directory, description, authors):
    if langchain_init:
        langchain_init()
    else:
        print("HELLO")
        type = "agent"
        if has_toml_file(directory):
            project_data = read_toml_file(os.path.join(directory, "pyproject.toml"))
            click.echo(
                f"Initializing project {project_data['name']} with description {project_data['description']}"
            )

            if check_uipath_project_already_initialized(directory):
                click.echo("Project already initialized")
                return

            configure_existing_project(
                directory,
                override_name=name,
                override_description=description,
                override_authors=authors,
            )

        else:
            click.echo(
                f"Initializing project {name} with description {description} in directory {directory}"
            )
            if not name:
                raise click.UsageError("Project name is required")

            os.makedirs(f"{directory}/{name}")
            os.makedirs(f"{directory}/{name}/.uipath")
            generate_init_file(f"{directory}/{name}")
            generate_requirements_file(f"{directory}/{name}")
            generate_project_toml_file(
                f"{directory}/{name}", name, description, authors
            )
            generate_seed_env_file(f"{directory}/{name}")
            generate_config_file(
                f"{directory}/{name}/.uipath",
                name,
                description,
                type,
                authors,
            )

            click.echo(
                f"Make sure to run `pip install -r {os.path.join(directory, 'requirements.txt')}` to install dependencies"
            )


# if __name__ == "__main__":
#     init()
