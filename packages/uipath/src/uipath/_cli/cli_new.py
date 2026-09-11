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
from .models.agent_frameworks import AgentFramework, installed_agent_frameworks
from .models.project_types import ProjectType

console = ConsoleLogger()

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


def _detect_agent_framework(installed: list[AgentFramework]) -> AgentFramework:
    """Resolve an unset --agent-framework from the installed integrations.

    Called with at most one installed integration (several error out before
    this): the single installed one wins, none installed errors with the
    list of frameworks and their packages.
    """
    if installed:
        framework = installed[0]
        console.info(f"Using the installed '{framework}' agent framework.")
        return framework
    packages = "\n".join(f"  {framework.package}" for framework in AgentFramework)
    console.error(
        "No agent framework integration is installed.\n"
        "Please install the package for the framework you want "
        "(`pip install <package>` or `uv add <package>`):\n\n" + packages
    )


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
    "otherwise; 'agent' requires one explicitly.",
)
@click.option(
    "--agent-framework",
    "agent_framework",
    type=click.Choice([f.value for f in AgentFramework]),
    default=None,
    help=(
        "Agent framework to scaffold for. Only valid together with `--type agent`; "
        "defaults to the framework whose integration package is installed."
    ),
)
@track_command("new")
def new(name: str, project_type: str, agent_framework: str | None):
    """Generate a quick-start project."""
    directory = os.getcwd()

    if not name:
        console.error(
            "Please specify a name for your project:\n`uipath new hello-world`"
        )

    scaffold_type = ProjectType(project_type)
    framework = AgentFramework(agent_framework) if agent_framework else None

    if framework and scaffold_type is not ProjectType.AGENT:
        console.error(
            "`--agent-framework` can only be used together with `--type agent`."
        )

    if framework is None and scaffold_type is not ProjectType.FUNCTION:
        installed = installed_agent_frameworks()
        if len(installed) > 1:
            console.error(
                "Multiple agent frameworks are installed: "
                + ", ".join(sorted(installed))
                + ".\nPick one with `--type agent --agent-framework <framework>`, "
                f"or run `uipath new {name} --type function` to create a "
                "function project."
            )
        if scaffold_type is ProjectType.AGENT:
            framework = _detect_agent_framework(installed)

    result = Middlewares.next(
        "new", name, project_type=scaffold_type, agent_framework=framework
    )

    if result.error_message:
        console.error(
            result.error_message, include_traceback=result.should_include_stacktrace
        )

    if result.info_message:
        console.info(result.info_message)

    if not result.should_continue:
        return

    if framework is not None:  # only set for agent scaffolds
        console.error(
            f"The '{framework.package}' package is required to scaffold a "
            f"'{framework}' agent.\n"
            "Please install it:\n\n"
            "  # Using pip:\n"
            f"  pip install {framework.package}\n\n"
            "  # Using uv:\n"
            f"  uv add {framework.package}\n\n"
            f"Or run `uipath new {name}` to create a function project."
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
