import importlib.metadata
import json
import os
import shutil
import uuid

import click

from uipath.platform.constants import PYTHON_CONFIGURATION_FILE, UIPATH_CONFIG_FILE

from ._telemetry import track_command
from ._utils._console import ConsoleLogger
from ._utils._constants import AGENT_FRAMEWORKS_DOCS_URL
from ._utils._project_files import resolve_existing_project_id
from .middlewares import MiddlewareResult, Middlewares
from .models.agent_frameworks import AgentFramework
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


def installed_agent_frameworks() -> list[AgentFramework]:
    """Agent frameworks that can scaffold a project, in discovery order."""
    packages: dict[str, str] = {}
    for entry_point in importlib.metadata.entry_points(group="uipath.middlewares"):
        if entry_point.dist is not None:
            packages.setdefault(entry_point.module.split(".")[0], entry_point.dist.name)

    frameworks = []
    for middleware in Middlewares.get("new"):
        package = packages.get(middleware.__module__.split(".")[0])
        if package is not None:
            frameworks.append(AgentFramework(package=package, scaffold=middleware))
    return frameworks


def _select_agent_framework(
    frameworks: list[AgentFramework], requested: str
) -> AgentFramework:
    """Resolve `--agent-framework` against what is installed."""
    for framework in frameworks:
        if requested == framework.package:
            return framework

    installed = (
        "Installed: "
        + ", ".join(sorted(framework.package for framework in frameworks))
        + "."
        if frameworks
        else "No agent framework is installed."
    )
    console.error(
        f"No installed agent framework matches '{requested}'.\n"
        f"{installed}\n"
        f"See {AGENT_FRAMEWORKS_DOCS_URL} for the supported frameworks and "
        "their packages."
    )


def _scaffold_agent(name: str, agent_framework: str | None) -> MiddlewareResult:
    """Offer the scaffold to the installed agent frameworks."""
    Middlewares.load_plugins()
    installed = installed_agent_frameworks()

    if agent_framework:
        # Dispatch to the chosen framework alone, so that another one cannot
        # claim the scaffold ahead of it.
        return _select_agent_framework(installed, agent_framework).scaffold(name)

    if len(installed) > 1:
        first = installed[0]
        console.warning(
            "Multiple agent frameworks are installed: "
            + ", ".join(framework.package for framework in installed)
            + f".\nScaffolding with the first one discovered: '{first.package}'. "
            f"To pick a different one, run `uipath new {name} --type agent "
            "--agent-framework <framework>`."
        )
        return first.scaffold(name)

    return Middlewares.next("new", name)


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
@click.option(
    "--agent-framework",
    "agent_framework",
    default=None,
    help="Agent framework to scaffold with, named by its package (e.g. "
    "`uipath-langchain`). Only valid together with `--type agent`; picks "
    "which framework scaffolds when several are installed.",
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

    if agent_framework and scaffold_type is not ProjectType.AGENT:
        console.error(
            "`--agent-framework` can only be used together with `--type agent`."
        )

    # Agent frameworks scaffold through the `new` middleware chain. A function
    # project never consults them.
    if scaffold_type is not ProjectType.FUNCTION:
        result = _scaffold_agent(name, agent_framework)

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
