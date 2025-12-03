import asyncio
import importlib.resources
import json
import logging
import os
import shutil
import uuid
from pathlib import Path

import click
from mermaid_builder.flowchart import (  # type: ignore[import-untyped]
    Chart,
    ChartDir,
    Link,
    Node,
    Subgraph,
)
from uipath.runtime import (
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeProtocol,
)
from uipath.runtime.schema import UiPathRuntimeGraph, UiPathRuntimeSchema

from uipath.platform.common import UiPathConfig

from .._utils.constants import ENV_TELEMETRY_ENABLED
from ..telemetry._constants import _PROJECT_KEY, _TELEMETRY_CONFIG_FILE
from ._utils._console import ConsoleLogger
from .middlewares import Middlewares
from .models.runtime_schema import Bindings
from .models.uipath_json_schema import UiPathJsonConfig

console = ConsoleLogger()
logger = logging.getLogger(__name__)

CONFIG_PATH = "uipath.json"


def create_telemetry_config_file(target_directory: str) -> None:
    """Create telemetry file if telemetry is enabled.

    Args:
        target_directory: The directory where the .uipath folder should be created.
    """
    telemetry_enabled = os.getenv(ENV_TELEMETRY_ENABLED, "true").lower() == "true"

    if not telemetry_enabled:
        return

    uipath_dir = os.path.join(target_directory, ".uipath")
    telemetry_file = os.path.join(uipath_dir, _TELEMETRY_CONFIG_FILE)

    if os.path.exists(telemetry_file):
        return

    os.makedirs(uipath_dir, exist_ok=True)
    telemetry_data = {_PROJECT_KEY: UiPathConfig.project_id or str(uuid.uuid4())}

    with open(telemetry_file, "w") as f:
        json.dump(telemetry_data, f, indent=4)


def generate_env_file(target_directory):
    env_path = os.path.join(target_directory, ".env")

    if not os.path.exists(env_path):
        relative_path = os.path.relpath(env_path, target_directory)
        with open(env_path, "w"):
            pass
        console.success(f"Created '{relative_path}' file.")


def generate_agent_md_file(
    target_directory: str, file_name: str, no_agents_md_override: bool
) -> bool:
    """Generate an agent-specific file from the packaged resource.

    Args:
        target_directory: The directory where the file should be created.
        file_name: The name of the file should be created.
        no_agents_md_override: Whether to override existing files.
    """
    target_path = os.path.join(target_directory, file_name)

    will_override = os.path.exists(target_path)

    if will_override and no_agents_md_override:
        console.success(
            f"File {click.style(target_path, fg='cyan')} already exists. Skipping."
        )
        return False

    try:
        source_path = importlib.resources.files("uipath._resources").joinpath(file_name)

        with importlib.resources.as_file(source_path) as s_path:
            shutil.copy(s_path, target_path)

        if will_override:
            logger.debug(f"File '{target_path}' has been overridden.")

        return will_override

    except Exception as e:
        console.warning(f"Could not create {file_name}: {e}")

    return False


def generate_agent_md_files(target_directory: str, no_agents_md_override: bool) -> None:
    """Generate an agent-specific file from the packaged resource.

    Args:
        target_directory: The directory where the files should be created.
        no_agents_md_override: Whether to override existing files.
    """
    agent_dir = os.path.join(target_directory, ".agent")
    os.makedirs(agent_dir, exist_ok=True)

    root_files = ["AGENTS.md", "CLAUDE.md"]

    agent_files = ["CLI_REFERENCE.md", "REQUIRED_STRUCTURE.md", "SDK_REFERENCE.md"]

    any_overridden = False

    for file_name in root_files:
        if generate_agent_md_file(target_directory, file_name, no_agents_md_override):
            any_overridden = True

    for file_name in agent_files:
        if generate_agent_md_file(agent_dir, file_name, no_agents_md_override):
            any_overridden = True

    if any_overridden:
        console.success(f"Updated {click.style('AGENTS.md', fg='cyan')} related files.")
        return

    console.success(f"Created {click.style('AGENTS.md', fg='cyan')} related files.")


def write_bindings_file(bindings: Bindings) -> Path:
    """Write bindings to a JSON file.

    Args:
        bindings: The Bindings object to write to file

    Returns:
        str: The path to the written bindings file
    """
    bindings_file_path = UiPathConfig.bindings_file_path
    with open(bindings_file_path, "w") as bindings_file:
        json_object = bindings.model_dump(by_alias=True, exclude_unset=True)
        json.dump(json_object, bindings_file, indent=4)

    return bindings_file_path


def write_entry_points_file(entry_points: list[UiPathRuntimeSchema]) -> Path:
    """Write entrypoints to a JSON file.

    Args:
        entry_points: The entrypoints list

    Returns:
        str: The path to the written entry_points file
    """
    json_object = {
        "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
        "$id": "entry-points.json",
        "entryPoints": [
            ep.model_dump(by_alias=True, exclude_unset=True) for ep in entry_points
        ],
    }

    entry_points_file_path = UiPathConfig.entry_points_file_path
    with open(entry_points_file_path, "w") as entry_points_file:
        json.dump(json_object, entry_points_file, indent=4)

    return entry_points_file_path


def write_mermaid_files(entry_points: list[UiPathRuntimeSchema]) -> list[Path]:
    """Write mermaid diagram files for each entrypoint.

    Args:
        entry_points: The entrypoints list with graph data

    Returns:
        list[Path]: List of paths to the written mermaid files
    """
    mermaid_paths = []

    for ep in entry_points:
        if not ep.graph:
            continue

        chart = Chart(direction=ChartDir.TB)

        _add_graph_to_chart(chart, ep.graph)

        mermaid_file_path = Path(os.getcwd()) / f"{ep.file_path}.mermaid"

        with open(mermaid_file_path, "w") as f:
            f.write(str(chart))

        mermaid_paths.append(mermaid_file_path)

    return mermaid_paths


def _add_graph_to_chart(chart: Chart | Subgraph, graph: UiPathRuntimeGraph) -> None:
    """Recursively add nodes and edges from UiPathRuntimeGraph to mermaid chart.

    Args:
        chart: The Chart or Subgraph to add nodes to
        graph: UiPathRuntimeGraph instance
    """
    node_objects = {}

    for node in graph.nodes:
        if node.subgraph:
            subgraph = Subgraph(title=node.name, direction=ChartDir.LR)
            _add_graph_to_chart(subgraph, node.subgraph)
            chart.add_subgraph(subgraph)
        else:
            mermaid_node = Node(title=node.name, id=node.id)
            chart.add_node(mermaid_node)
            node_objects[node.id] = mermaid_node

    for edge in graph.edges:
        link = Link(
            src=edge.source, dest=edge.target, text=edge.label if edge.label else None
        )
        chart.add_link(link)


@click.command()
@click.option(
    "--no-agents-md-override",
    is_flag=True,
    required=False,
    default=False,
    help="Won't override existing .agent files and AGENTS.md file.",
)
def init(no_agents_md_override: bool) -> None:
    """Initialize the project."""
    with console.spinner("Initializing UiPath project ..."):
        current_directory = os.getcwd()
        generate_env_file(current_directory)
        create_telemetry_config_file(current_directory)

        async def initialize() -> None:
            try:
                # Create uipath.json if it doesn't exist
                config_path = UiPathConfig.config_file_path
                if not config_path.exists():
                    config = UiPathJsonConfig.create_default()
                    config.save_to_file(config_path)
                    console.success(f"Created '{config_path}' file.")
                else:
                    console.info(f"'{config_path}' already exists, skipping.")

                # Create bindings.json if it doesn't exist
                bindings_path = UiPathConfig.bindings_file_path
                if not bindings_path.exists():
                    bindings_path = write_bindings_file(
                        Bindings(version="2.0", resources=[])
                    )
                    console.success(f"Created '{bindings_path}' file.")
                else:
                    console.info(f"'{bindings_path}' already exists, skipping.")

                # Always create/update entry-points.json from runtime schemas
                factory: UiPathRuntimeFactoryProtocol = (
                    UiPathRuntimeFactoryRegistry.get()
                )
                entry_point_schemas: list[UiPathRuntimeSchema] = []

                try:
                    entrypoints = factory.discover_entrypoints()

                    if not entrypoints:
                        console.warning(
                            'No function entrypoints found. Add them to `uipath.json` under "functions": {"my_function": "src/main.py:main"}'
                        )

                    # Gather schemas from all discovered runtimes
                    for entrypoint_name in entrypoints:
                        runtime: UiPathRuntimeProtocol | None = None
                        try:
                            runtime = await factory.new_runtime(
                                entrypoint_name, runtime_id="default"
                            )
                            schema = await runtime.get_schema()
                            entry_point_schemas.append(schema)
                        finally:
                            if runtime:
                                await runtime.dispose()
                finally:
                    await factory.dispose()

                # Write entry-points.json with all schemas
                entry_points_path = write_entry_points_file(entry_point_schemas)
                console.success(
                    f"Created '{entry_points_path}' file with {len(entry_point_schemas)} entrypoint(s)."
                )

                # Write mermaid diagrams for each entrypoint
                mermaid_paths = write_mermaid_files(entry_point_schemas)
                if mermaid_paths and len(mermaid_paths) > 0:
                    console.success(
                        f"Created {len(mermaid_paths)} mermaid diagram file(s)."
                    )

            except Exception as e:
                console.error(
                    f"Error during initialization:\n{str(e)}", include_traceback=True
                )

        asyncio.run(initialize())

        result = Middlewares.next(
            "init",
            options={
                "no_agents_md_override": no_agents_md_override,
            },
        )

        if result.error_message:
            console.error(
                result.error_message, include_traceback=result.should_include_stacktrace
            )

        if result.info_message:
            console.info(result.info_message)

        if not result.should_continue:
            return

        generate_agent_md_files(current_directory, no_agents_md_override)
