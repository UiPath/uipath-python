import importlib.metadata
import json
import os
import shutil
import uuid

import click

from uipath.platform.constants import PYTHON_CONFIGURATION_FILE, UIPATH_CONFIG_FILE

from ._telemetry import track_command
from ._utils._console import ConsoleLogger
from ._utils._project_files import resolve_existing_project_id
from .middlewares import Middlewares
from .models.project_types import ProjectType

console = ConsoleLogger()

# Agent frameworks are documented, not enumerated in code: each integration
# ships its own `new` middleware, so the CLI knows which ones are installed
# but cannot know which ones exist.
AGENT_FRAMEWORKS_DOCS_URL = "https://uipath.github.io/uipath-python/core/agents/"

# The `uipath` minor release that scaffolded projects are pinned to.
# Deliberately a constant: the guard test in tests/cli/test_new.py fails on
# every minor bump so the scaffold (pin, template, hints) gets reviewed
# alongside the release rather than drifting silently.
UIPATH_SCAFFOLD_MINOR = "2.14"


def generate_script(target_directory):
    template_path = os.path.join(
        os.path.dirname(__file__), "_templates/main.py.template"
    )
    target_path = os.path.join(target_directory, "main.py")

    shutil.copyfile(template_path, target_path)


def generate_pyproject(target_directory, project_name):
    project_toml_path = os.path.join(target_directory, PYTHON_CONFIGURATION_FILE)
    major, minor = (int(part) for part in UIPATH_SCAFFOLD_MINOR.split("."))
    toml_content = f"""[project]
name = "{project_name}"
version = "0.0.1"
description = "{project_name}"
authors = [{{ name = "John Doe", email = "john.doe@myemail.com" }}]
dependencies = [
    "uipath>={major}.{minor}.0, <{major}.{minor + 1}.0"
]
requires-python = ">=3.11"
"""

    with open(project_toml_path, "w") as f:
        f.write(toml_content)


def generate_uipath_json(target_directory):
    uipath_json_path = os.path.join(target_directory, UIPATH_CONFIG_FILE)
    project_id = resolve_existing_project_id(target_directory) or str(uuid.uuid4())
    uipath_config = {"id": project_id, "functions": {"main": "main.py:main"}}

    with open(uipath_json_path, "w") as f:
        json.dump(uipath_config, f, indent=2)


def _installed_agent_framework_packages() -> list[str]:
    """Packages of the installed agent frameworks that can scaffold a project.

    Derived from the registered `new` middlewares rather than from a list of
    known frameworks, so a framework the CLI has never heard of is named
    correctly and a new one needs no change here.
    """
    modules = {
        middleware.__module__.split(".")[0] for middleware in Middlewares.get("new")
    }
    packages: set[str] = set()
    for entry_point in importlib.metadata.entry_points(group="uipath.middlewares"):
        module = entry_point.module.split(".")[0]
        if module in modules and entry_point.dist is not None:
            packages.add(entry_point.dist.name)
            modules.discard(module)
    # A middleware registered in-process rather than through an entry point has
    # no distribution to name; its module is the most accurate thing left.
    return sorted(packages | modules)


@click.command()
@click.argument("name", type=str, default="")
@click.option(
    "--type",
    "project_type",
    type=click.Choice([t.value for t in ProjectType]),
    default=ProjectType.AUTO.value,
    show_default=True,
    help="Project type to scaffold. 'auto' scaffolds an agent when an agent "
    "framework package (e.g. uipath-langchain) is installed and a function "
    "otherwise; 'function' always scaffolds a function; 'agent' scaffolds an "
    "agent and fails when no agent framework is installed.",
)
@track_command("new")
def new(name: str, project_type: str):
    """Generate a quick-start project."""
    directory = os.getcwd()

    if not name:
        console.error(
            "Please specify a name for your project:\n`uipath new hello-world`"
        )

    scaffold_type = ProjectType(project_type)

    # Agent frameworks scaffold through the `new` middleware chain. A function
    # project never consults them, so an installed framework can no longer make
    # the base scaffold unreachable (#1543).
    if scaffold_type is not ProjectType.FUNCTION:
        Middlewares.load_plugins()
        installed = _installed_agent_framework_packages()
        if len(installed) > 1:
            console.error(
                "Multiple agent frameworks are installed: "
                + ", ".join(installed)
                + ".\nKeep the one you want to scaffold with in this environment, "
                f"or run `uipath new {name} --type function` to create a "
                "function project."
            )

        result = Middlewares.next("new", name)

        if result.error_message:
            console.error(
                result.error_message, include_traceback=result.should_include_stacktrace
            )

        if result.info_message:
            console.info(result.info_message)

        if not result.should_continue:
            return  # an agent framework scaffolded the project

        if scaffold_type is ProjectType.AGENT:
            console.error(
                "No agent framework is installed, so there is nothing to "
                "scaffold an agent with.\n"
                "Install the framework you want to use and run this command "
                f"again — see {AGENT_FRAMEWORKS_DOCS_URL} for the supported "
                "frameworks and their packages.\n"
                f"Or run `uipath new {name} --type function` to create a "
                "function project."
            )

    with console.spinner(f"Creating new project {name} in current directory ..."):
        generate_script(directory)
        console.success("Created 'main.py' file.")
        generate_pyproject(directory, name)
        console.success(f"Created '{PYTHON_CONFIGURATION_FILE}' file.")
        generate_uipath_json(directory)
        console.success(f"Created '{UIPATH_CONFIG_FILE}' file.")
        init_command = """uipath init"""
        run_command = """uipath run main '{"message": "Hello World!"}'"""
        console.hint(f"""Initialize project: {click.style(init_command, fg="cyan")}""")
        console.hint(f"""Run project: {click.style(run_command, fg="cyan")}""")


if __name__ == "__main__":
    new()
