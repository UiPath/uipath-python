import asyncio
import enum
import importlib.resources
import json
import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

import click
from graphtty import RenderOptions, render
from graphtty.themes import TOKYO_NIGHT
from graphtty.types import AsciiGraph
from mermaid_builder.flowchart import (  # type: ignore[import-untyped]
    Chart,
    ChartDir,
    Link,
    Node,
    Subgraph,
)

from uipath.platform.common import UiPathConfig
from uipath.runtime import (
    UiPathRuntimeContext,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeProtocol,
)
from uipath.runtime.schema import UiPathRuntimeGraph, UiPathRuntimeSchema

from .._utils.constants import ENV_TELEMETRY_ENABLED
from ..telemetry._constants import _PROJECT_KEY, _TELEMETRY_CONFIG_FILE
from ._telemetry import track_command
from ._utils._common import determine_project_type
from ._utils._console import ConsoleLogger
from ._utils._constants import AGENT_INITIAL_CODE_VERSION, SCHEMA_VERSION
from ._utils._project_files import read_toml_project
from .middlewares import Middlewares
from .models.runtime_schema import Bindings, EntryPoint
from .models.uipath_json_schema import UiPathJsonConfig

console = ConsoleLogger()
logger = logging.getLogger(__name__)

CONFIG_PATH = "uipath.json"

GRAPH_INDENT = "    "


class Action(str, enum.Enum):
    CREATED = "Created"
    UPDATED = "Updated"


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
        console.success(f"{Action.CREATED.value} '{relative_path}' file.")


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
    """Generate AGENTS.md related files and Claude Code skills.

    Args:
        target_directory: The directory where the files should be created.
        no_agents_md_override: Whether to override existing files.
    """
    agent_dir = os.path.join(target_directory, ".agent")
    os.makedirs(agent_dir, exist_ok=True)
    claude_commands_dir = os.path.join(target_directory, ".claude", "commands")
    os.makedirs(claude_commands_dir, exist_ok=True)

    files_to_create = {
        target_directory: ["AGENTS.md", "CLAUDE.md"],
        agent_dir: ["CLI_REFERENCE.md", "REQUIRED_STRUCTURE.md", "SDK_REFERENCE.md"],
        claude_commands_dir: ["new-agent.md", "eval.md"],
    }

    any_overridden = False
    for directory, filenames in files_to_create.items():
        for filename in filenames:
            if generate_agent_md_file(directory, filename, no_agents_md_override):
                any_overridden = True

    if any_overridden:
        console.success(
            f"{Action.UPDATED.value} {click.style('AGENTS.md', fg='cyan')} files and Claude Code skills."
        )
        return

    console.success(
        f"{Action.CREATED.value} {click.style('AGENTS.md', fg='cyan')} files and Claude Code skills."
    )


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
            ep.model_dump(
                by_alias=True,
                exclude_unset=True,
            )
            for ep in entry_points
        ],
    }

    entry_points_file_path = UiPathConfig.entry_points_file_path
    with open(entry_points_file_path, "w") as entry_points_file:
        json.dump(json_object, entry_points_file, indent=4)

    return entry_points_file_path


def write_uiproj_file(
    entry_point_schemas: list[UiPathRuntimeSchema],
    current_directory: str,
) -> None:
    """Write project.uiproj file, warning if the project type changed.

    Args:
        entry_point_schemas: The entrypoint schemas from runtime discovery.
        current_directory: The project root directory.

    """
    entry_point_models = [
        EntryPoint.model_validate(ep.model_dump(by_alias=True, exclude_unset=True))
        for ep in entry_point_schemas
    ]
    project_type = determine_project_type(entry_point_models).capitalize()

    toml_data = read_toml_project(os.path.join(current_directory, "pyproject.toml"))
    project_name = toml_data["name"]
    project_description = toml_data.get("description")

    uiproj_file_path = Path(current_directory) / str(UiPathConfig.uiproj_file_path)
    if uiproj_file_path.exists():
        action = Action.UPDATED.value
        with open(uiproj_file_path, "r") as f:
            existing = json.load(f)
        existing_type = existing.get("ProjectType")
        if existing_type and existing_type != project_type:
            console.warning(
                f'Project type changed from "{existing_type}" to "{project_type}".'
            )
    else:
        action = Action.CREATED.value

    json_object = {
        "ProjectType": project_type,
        "Name": project_name,
        "Description": project_description,
        "MainFile": None,
    }

    with open(uiproj_file_path, "w") as f:
        json.dump(json_object, f, indent=2)

    console.success(f"{action} '{UiPathConfig.uiproj_file_path}' file.")


def write_studio_metadata_file(directory: str) -> None:
    """Write studio_metadata.json with initial codeVersion and schemaVersion.

    Args:
        directory: The project root directory.
    """
    local_metadata_file = os.path.join(
        directory, str(UiPathConfig.studio_metadata_file_path)
    )
    if os.path.exists(local_metadata_file):
        return

    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "codeVersion": AGENT_INITIAL_CODE_VERSION,
    }
    os.makedirs(os.path.dirname(local_metadata_file), exist_ok=True)
    with open(local_metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    console.success(
        f"{Action.CREATED.value} '{os.path.relpath(local_metadata_file, directory)}' file."
    )


MERMAID_FILE_HEADER = (
    "%% AUTO-GENERATED by `uipath init`. Do not edit manually.\n"
    "%% Regenerated on every `uipath init`.\n"
)


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
            f.write(MERMAID_FILE_HEADER)
            f.write(str(chart))

        mermaid_paths.append(mermaid_file_path)

    return mermaid_paths


_MERMAID_ID_INVALID_CHARS = re.compile(r"[^a-zA-Z0-9_]+")


def _sanitize_mermaid_id(node_id: str) -> str:
    """Replace characters invalid in Mermaid node IDs with underscores.

    `UiPathRuntimeNode.id` uses `file.py:line` so the value can double as a
    breakpoint location. Mermaid treats `.` and `:` as syntax, so the raw ID
    breaks the flowchart parser — sanitize before emitting.
    """
    return _MERMAID_ID_INVALID_CHARS.sub("_", node_id)


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
            mermaid_id = _sanitize_mermaid_id(node.id)
            mermaid_node = Node(title=node.name, id=mermaid_id)
            chart.add_node(mermaid_node)
            node_objects[node.id] = mermaid_node

    for edge in graph.edges:
        link = Link(
            src=_sanitize_mermaid_id(edge.source),
            dest=_sanitize_mermaid_id(edge.target),
            text=edge.label if edge.label else None,
        )
        chart.add_link(link)


def _enrich_graph_node_descriptions(graph_data: dict[str, Any]) -> None:
    """Enrich graph node descriptions with metadata (model names, tool names).

    Args:
        graph_data: The graph data dict to mutate in-place.
    """
    node: dict[str, Any]
    for node in graph_data.get("nodes", []):
        meta = node.get("metadata") or {}
        if not node.get("description"):
            if node.get("type") == "model" and "model_name" in meta:
                node["description"] = meta["model_name"]
            elif node.get("type") == "tool" and "tool_names" in meta:
                names = meta["tool_names"]
                if isinstance(names, list):
                    node["description"] = ", ".join(names)
                elif isinstance(names, str):
                    node["description"] = names


def _render_graph(rendered: str, indent: str = GRAPH_INDENT) -> str:
    """Indent every line of the rendered graph for visual containment.

    Args:
        rendered: The raw rendered graph string.
        indent: The indent prefix for each line.

    Returns:
        The indented graph string.
    """
    return "\n".join(indent + line for line in rendered.splitlines())


def _display_entrypoint_graphs(entry_point_schemas: list[UiPathRuntimeSchema]) -> None:
    """Render and display ASCII graphs for all entrypoints that have graph data.

    Args:
        entry_point_schemas: List of runtime schemas with optional graph data.
    """
    graphs_to_render = [ep for ep in entry_point_schemas if ep.graph and ep.graph.nodes]

    if not graphs_to_render:
        return

    click.echo()

    for entrypoint_schema in graphs_to_render:
        if entrypoint_schema.graph is None:
            continue
        title = entrypoint_schema.file_path or "Agent"
        click.echo(click.style(f"  Entrypoint: {title}", fg="cyan", bold=True))
        click.echo(click.style("  " + "─" * 50, fg="bright_black"))
        click.echo()

        try:
            graph_data = entrypoint_schema.graph.model_dump()
            _enrich_graph_node_descriptions(graph_data)

            ascii_graph = AsciiGraph(**graph_data)
            options = RenderOptions(theme=TOKYO_NIGHT, max_breadth=3, max_depth=5)
            rendered = render(ascii_graph, options)
            click.echo(_render_graph(rendered))
        except Exception:
            pass

        click.echo()


@click.command()
@click.option(
    "--no-agents-md-override",
    is_flag=True,
    required=False,
    default=False,
    help="Won't override existing .agent files and AGENTS.md file.",
)
@track_command("initialize")
def init(no_agents_md_override: bool) -> None:
    """Initialize the project."""
    with console.spinner("Initializing UiPath project ..."):
        current_directory = os.getcwd()
        generate_env_file(current_directory)
        create_telemetry_config_file(current_directory)

        async def initialize() -> list[UiPathRuntimeSchema]:
            try:
                # Create uipath.json if it doesn't exist
                config_path = UiPathConfig.config_file_path
                if not config_path.exists():
                    config = UiPathJsonConfig.create_default()
                    config.save_to_file(config_path)
                    console.success(f"{Action.CREATED.value} '{config_path}' file.")
                else:
                    console.info(f"'{config_path}' already exists, skipping.")

                # Create bindings.json if it doesn't exist
                bindings_path = UiPathConfig.bindings_file_path
                if not bindings_path.exists():
                    bindings_path = write_bindings_file(
                        Bindings(version="2.0", resources=[])
                    )
                    console.success(f"{Action.CREATED.value} '{bindings_path}' file.")
                else:
                    console.info(f"'{bindings_path}' already exists, skipping.")

                # Always create/update entry-points.json from runtime schemas
                factory: UiPathRuntimeFactoryProtocol = (
                    UiPathRuntimeFactoryRegistry.get(
                        context=UiPathRuntimeContext(command="init")
                    )
                )
                entry_point_schemas: list[UiPathRuntimeSchema] = []

                try:
                    entrypoints = factory.discover_entrypoints()

                    if not entrypoints:
                        console.warning(
                            'No entrypoints found. Add them to `uipath.json` under "functions" or "agents": {"my_function": "src/main.py:main"}'
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
                    f"{Action.CREATED.value} '{entry_points_path}' file with {len(entry_point_schemas)} entrypoint(s)."
                )

                # Write mermaid diagrams for each entrypoint
                mermaid_paths = write_mermaid_files(entry_point_schemas)
                if mermaid_paths and len(mermaid_paths) > 0:
                    console.success(
                        f"{Action.CREATED.value} {len(mermaid_paths)} mermaid diagram file(s)."
                    )

                write_uiproj_file(entry_point_schemas, current_directory)
                write_studio_metadata_file(current_directory)

                return entry_point_schemas

            except Exception as e:
                console.error(f"Error during initialization:\n{e}")
                return []

        entry_point_schemas = asyncio.run(initialize())

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
            _display_entrypoint_graphs(entry_point_schemas)
            return

        generate_agent_md_files(current_directory, no_agents_md_override)

        _display_entrypoint_graphs(entry_point_schemas)
