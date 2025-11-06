# type: ignore
import json
import os
import uuid
import zipfile
from string import Template

import click
from pydantic import TypeAdapter

from uipath._cli.models.runtime_schema import Bindings, RuntimeSchema
from uipath._config import UiPathConfig

from ..telemetry import track
from ..telemetry._constants import _PROJECT_KEY, _TELEMETRY_CONFIG_FILE
from ._utils._console import ConsoleLogger
from ._utils._project_files import (
    files_to_include,
    read_toml_project,
    validate_config,
)
from ._utils._uv_helpers import handle_uv_operations

console = ConsoleLogger()

schema = "https://cloud.uipath.com/draft/2024-12/entry-point"


def get_project_id() -> str:
    """Get project ID from telemetry file if it exists, otherwise generate a new one.

    Returns:
        Project ID string (either from telemetry file or newly generated).
    """
    # first check if this is a studio project
    if project_id := UiPathConfig.project_id:
        return project_id

    telemetry_file = os.path.join(".uipath", _TELEMETRY_CONFIG_FILE)

    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file, "r") as f:
                telemetry_data = json.load(f)
                project_id = telemetry_data.get(_PROJECT_KEY)
                if project_id:
                    return project_id
        except (json.JSONDecodeError, IOError):
            pass

    return str(uuid.uuid4())


def generate_operate_file(entryPoints, dependencies=None, is_conversational=False):
    project_id = get_project_id()

    first_entry = entryPoints[0]
    file_path = first_entry["filePath"]
    type = first_entry["type"]

    operate_json_data = {
        "$schema": schema,
        "projectId": project_id,
        "main": file_path,
        "contentType": type,
        "targetFramework": "Portable",
        "targetRuntime": "python",
        "runtimeOptions": {
            "requiresUserInteraction": False,
            "isAttended": False,
            "isConversational": is_conversational,
        },
    }

    # Add dependencies if provided
    if dependencies:
        operate_json_data["dependencies"] = dependencies

    return operate_json_data


def generate_entrypoints_file(entryPoints):
    entrypoint_json_data = {
        "$schema": schema,
        "$id": "entry-points.json",
        "entryPoints": entryPoints,
    }

    return entrypoint_json_data


def generate_bindings_content() -> Bindings:
    return Bindings(
        version="2.0",
        resources=[],
    )


def generate_content_types_content():
    templates_path = os.path.join(
        os.path.dirname(__file__), "_templates", "[Content_Types].xml.template"
    )
    with open(templates_path, "r") as file:
        content_types_content = file.read()
    return content_types_content


def generate_nuspec_content(projectName, packageVersion, description, authors):
    variables = {
        "packageName": projectName,
        "packageVersion": packageVersion,
        "description": description,
        "authors": authors,
    }
    templates_path = os.path.join(
        os.path.dirname(__file__), "_templates", "package.nuspec.template"
    )
    with open(templates_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return Template(content).substitute(variables)


def generate_rels_content(nuspecPath, psmdcpPath):
    # /package/services/metadata/core-properties/254324ccede240e093a925f0231429a0.psmdcp
    templates_path = os.path.join(
        os.path.dirname(__file__), "_templates", ".rels.template"
    )
    nuspecId = "R" + str(uuid.uuid4()).replace("-", "")[:16]
    psmdcpId = "R" + str(uuid.uuid4()).replace("-", "")[:16]
    variables = {
        "nuspecPath": nuspecPath,
        "nuspecId": nuspecId,
        "psmdcpPath": psmdcpPath,
        "psmdcpId": psmdcpId,
    }
    with open(templates_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return Template(content).substitute(variables)


def generate_psmdcp_content(projectName, version, description, authors):
    templates_path = os.path.join(
        os.path.dirname(__file__), "_templates", ".psmdcp.template"
    )

    token = str(uuid.uuid4()).replace("-", "")[:32]
    random_file_name = f"{uuid.uuid4().hex[:16]}.psmdcp"
    variables = {
        "creator": authors,
        "description": description,
        "packageVersion": version,
        "projectName": projectName,
        "publicKeyToken": token,
    }
    with open(templates_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    return [random_file_name, Template(content).substitute(variables)]


def generate_package_descriptor_content(entryPoints):
    files = {
        "operate.json": "content/operate.json",
        "entry-points.json": "content/entry-points.json",
        "bindings.json": "content/bindings_v2.json",
    }

    for entry in entryPoints:
        files[entry["filePath"]] = entry["filePath"]

    package_descriptor_content = {
        "$schema": "https://cloud.uipath.com/draft/2024-12/package-descriptor",
        "files": files,
    }

    return package_descriptor_content


def pack_fn(
    runtime_schema: RuntimeSchema,
    toml_data: dict,
    directory: str,
    include_uv_lock: bool = True,
):
    is_conversational = (
        runtime_schema.settings.get("isConversational", False)
        if runtime_schema.settings
        else False
    )

    if not isinstance(is_conversational, bool | None):
        console.error("isConversational must be a boolean value")

    # Get entryPoints from RuntimeSchema
    entryPoints = [ep.model_dump(by_alias=True) for ep in runtime_schema.entrypoints]

    # Extract fields from toml_data
    projectName = toml_data["name"]
    description = toml_data["description"]
    version = toml_data["version"]
    authors = toml_data["authors"]
    dependencies = toml_data.get("dependencies")

    operate_file = generate_operate_file(
        entryPoints, dependencies, is_conversational or False
    )
    entrypoints_file = generate_entrypoints_file(entryPoints)

    # For backwards compatibility. should be removed
    if not len(runtime_schema.bindings.resources):
        # Try to read bindings from bindings.json
        bindings_path = os.path.join(directory, str(UiPathConfig.bindings_file_path))
        if os.path.exists(bindings_path):
            with open(bindings_path, "r") as f:
                bindings_data = TypeAdapter(Bindings).validate_python(json.load(f))
                runtime_schema.bindings = bindings_data

    content_types_content = generate_content_types_content()
    [psmdcp_file_name, psmdcp_content] = generate_psmdcp_content(
        projectName, version, description, authors
    )
    nuspec_content = generate_nuspec_content(projectName, version, description, authors)
    rels_content = generate_rels_content(
        f"/{projectName}.nuspec",
        f"/package/services/metadata/core-properties/{psmdcp_file_name}",
    )
    package_descriptor_content = generate_package_descriptor_content(entryPoints)

    # Create .uipath directory if it doesn't exist
    os.makedirs(".uipath", exist_ok=True)

    with zipfile.ZipFile(
        f".uipath/{projectName}.{version}.nupkg", "w", zipfile.ZIP_DEFLATED
    ) as z:
        # Add metadata files
        z.writestr(
            f"./package/services/metadata/core-properties/{psmdcp_file_name}",
            psmdcp_content,
        )
        z.writestr("[Content_Types].xml", content_types_content)
        z.writestr(
            "content/package-descriptor.json",
            json.dumps(package_descriptor_content, indent=4),
        )
        z.writestr("content/operate.json", json.dumps(operate_file, indent=4))
        z.writestr("content/entry-points.json", json.dumps(entrypoints_file, indent=4))
        z.writestr(
            "content/bindings_v2.json",
            json.dumps(runtime_schema.bindings.model_dump(by_alias=True), indent=4),
        )
        z.writestr(f"{projectName}.nuspec", nuspec_content)
        z.writestr("_rels/.rels", rels_content)

        files = files_to_include(runtime_schema.settings, directory, include_uv_lock)

        for file in files:
            if file.is_binary:
                # Read binary files in binary mode
                with open(file.file_path, "rb") as f:
                    z.writestr(f"content/{file.relative_path}", f.read())
            else:
                try:
                    # Try UTF-8 first
                    with open(file.file_path, "r", encoding="utf-8") as f:
                        z.writestr(f"content/{file.relative_path}", f.read())
                except UnicodeDecodeError:
                    # If UTF-8 fails, try with utf-8-sig (for files with BOM)
                    try:
                        with open(file.file_path, "r", encoding="utf-8-sig") as f:
                            z.writestr(f"content/{file.relative_path}", f.read())
                    except UnicodeDecodeError:
                        # If that also fails, try with latin-1 as a fallback
                        with open(file.file_path, "r", encoding="latin-1") as f:
                            z.writestr(f"content/{file.relative_path}", f.read())


def display_project_info(config):
    max_label_length = max(
        len(label) for label in ["Name", "Version", "Description", "Authors"]
    )

    max_length = 100
    description = config["description"]
    if len(description) >= max_length:
        description = description[: max_length - 3] + " ..."

    console.log(f"{'Name'.ljust(max_label_length)}: {config['project_name']}")
    console.log(f"{'Version'.ljust(max_label_length)}: {config['version']}")
    console.log(f"{'Description'.ljust(max_label_length)}: {description}")
    console.log(f"{'Authors'.ljust(max_label_length)}: {config['authors']}")


@click.command()
@click.argument(
    "root", type=click.Path(exists=True, file_okay=False, dir_okay=True), default="."
)
@click.option(
    "--nolock",
    is_flag=True,
    help="Skip running uv lock and exclude uv.lock from the package",
)
@track
def pack(root, nolock):
    """Pack the project."""
    config_path = os.path.join(root, "uipath.json")
    if not os.path.exists(config_path):
        console.error(
            "uipath.json not found. Please run `uipath init` in the project directory."
        )

    with open(config_path, "r") as f:
        runtime_schema = TypeAdapter(RuntimeSchema).validate_python(json.load(f))

    # Read pyproject.toml
    toml_path = os.path.join(root, "pyproject.toml")
    if not os.path.exists(toml_path):
        console.error("pyproject.toml not found.")
    toml_data = read_toml_project(toml_path)

    # Add project_name key for validate_config (it expects this key)
    toml_data["project_name"] = toml_data["name"]

    validate_config(toml_data)

    with console.spinner("Packaging project ..."):
        try:
            # Handle uv operations before packaging, unless nolock is specified
            if not nolock:
                handle_uv_operations(root)

            pack_fn(
                runtime_schema,
                toml_data,
                root,
                include_uv_lock=not nolock,
            )
            display_project_info(toml_data)
            console.success("Project successfully packaged.")

        except Exception as e:
            console.error(
                f"Failed to create package {toml_data['project_name']}.{toml_data['version']}: {str(e)}"
            )


if __name__ == "__main__":
    pack()
