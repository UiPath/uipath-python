# type: ignore
import json
import os
import uuid
import zipfile
from string import Template

import click

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .parse_ast import generate_bindings_json

schema = "https://cloud.uipath.com/draft/2024-12/entry-point"


def validate_config_structure(config_data):
    required_fields = ["entryPoints"]
    for field in required_fields:
        if field not in config_data:
            raise Exception(f"uipath.json is missing the required field: {field}")


def check_config(directory):
    config_path = os.path.join(directory, "uipath.json")
    toml_path = os.path.join(directory, "pyproject.toml")

    if not os.path.isfile(config_path):
        raise Exception("uipath.json not found, please run `uipath init`")
    if not os.path.isfile(toml_path):
        raise Exception("pyproject.toml not found")

    with open(config_path, "r") as config_file:
        config_data = json.load(config_file)

    validate_config_structure(config_data)

    toml_data = read_toml_project(toml_path)

    return {
        "project_name": toml_data["name"],
        "description": toml_data["description"],
        "entryPoints": config_data["entryPoints"],
        "version": toml_data["version"],
        "authors": toml_data["authors"],
    }


def generate_operate_file(entryPoints):
    project_id = str(uuid.uuid4())

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
        "runtimeOptions": {"requiresUserInteraction": False, "isAttended": False},
    }

    return operate_json_data


def generate_entrypoints_file(entryPoints):
    entrypoint_json_data = {
        "$schema": schema,
        "$id": "entry-points.json",
        "entryPoints": entryPoints,
    }

    return entrypoint_json_data


def generate_bindings_content():
    bindings_content = {"version": "2.0", "resources": []}

    return bindings_content


def get_proposed_version(directory):
    output_dir = os.path.join(directory, ".uipath")
    if not os.path.exists(output_dir):
        return None

    # Get all .nupkg files
    nupkg_files = [f for f in os.listdir(output_dir) if f.endswith(".nupkg")]
    if not nupkg_files:
        return None

    # Sort by modification time to get most recent
    latest_file = max(
        nupkg_files, key=lambda f: os.path.getmtime(os.path.join(output_dir, f))
    )

    # Extract version from filename
    # Remove .nupkg extension first
    name_version = latest_file[:-6]
    # Find 3rd last occurrence of . by splitting and joining parts
    parts = name_version.split(".")
    if len(parts) >= 3:
        version = ".".join(parts[-3:])
    else:
        version = name_version

    # Increment patch version by 1
    try:
        major, minor, patch = version.split(".")
        new_version = f"{major}.{minor}.{int(patch) + 1}"
        return new_version
    except Exception:
        return "0.0.1"


def generate_content_types_content():
    templates_path = os.path.join(
        os.path.dirname(__file__), "templates", "[Content_Types].xml.template"
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
        os.path.dirname(__file__), "templates", "package.nuspec.template"
    )
    with open(templates_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return Template(content).substitute(variables)


def generate_rels_content(nuspecPath, psmdcpPath):
    # /package/services/metadata/core-properties/254324ccede240e093a925f0231429a0.psmdcp
    templates_path = os.path.join(
        os.path.dirname(__file__), "templates", ".rels.template"
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
        os.path.dirname(__file__), "templates", ".psmdcp.template"
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


def pack_fn(projectName, description, entryPoints, version, authors, directory):
    operate_file = generate_operate_file(entryPoints)
    entrypoints_file = generate_entrypoints_file(entryPoints)

    # Get bindings from uipath.json if available
    config_path = os.path.join(directory, "uipath.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config_data = json.load(f)
            if "bindings" in config_data:
                bindings_content = config_data["bindings"]
            else:
                # Fall back to generating bindings from the first entry point
                bindings_content = generate_bindings_json(entryPoints[0]["filePath"])
    else:
        # Fall back to generating bindings from the first entry point
        bindings_content = generate_bindings_json(entryPoints[0]["filePath"])

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

    # Define the allowlist of file extensions to include
    file_extensions_allowlist = [".py", ".mermaid", ".json"]

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
        z.writestr("content/bindings_v2.json", json.dumps(bindings_content, indent=4))
        z.writestr(f"{projectName}.nuspec", nuspec_content)
        z.writestr("_rels/.rels", rels_content)

        # Walk through directory and add all files with extensions in the allowlist
        for root, dirs, files in os.walk(directory):
            # Skip all directories that start with .
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                file_extension = os.path.splitext(file)[1].lower()
                if file_extension in file_extensions_allowlist:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, directory)
                    try:
                        # Try UTF-8 first
                        with open(file_path, "r", encoding="utf-8") as f:
                            z.writestr(f"content/{rel_path}", f.read())
                    except UnicodeDecodeError:
                        # If UTF-8 fails, try with utf-8-sig (for files with BOM)
                        try:
                            with open(file_path, "r", encoding="utf-8-sig") as f:
                                z.writestr(f"content/{rel_path}", f.read())
                        except UnicodeDecodeError:
                            # If that also fails, try with latin-1 as a fallback
                            with open(file_path, "r", encoding="latin-1") as f:
                                z.writestr(f"content/{rel_path}", f.read())

        optional_files = ["pyproject.toml", "README.md"]
        for file in optional_files:
            file_path = os.path.join(directory, file)
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        z.writestr(f"content/{file}", f.read())
                except UnicodeDecodeError:
                    with open(file_path, "r", encoding="latin-1") as f:
                        z.writestr(f"content/{file}", f.read())


def read_toml_project(file_path: str) -> dict[str, any]:
    with open(file_path, "rb") as f:
        content = tomllib.load(f)
        return {
            "name": content["project"]["name"],
            "description": content["project"]["description"],
            "version": content["project"]["version"],
            "authors": content["project"].get("authors", [{"name": ""}])[0]["name"],
        }


def get_project_version(directory):
    toml_path = os.path.join(directory, "pyproject.toml")
    if not os.path.exists(toml_path):
        click.echo("Warning: No pyproject.toml found. Using default version 0.0.1")
        return "0.0.1"
    toml_data = read_toml_project(toml_path)
    return toml_data["version"]


@click.command()
@click.argument("root", type=str, default="./")
def pack(root):
    version = get_project_version(root)

    while not os.path.isfile(os.path.join(root, "uipath.json")):
        click.echo(
            "uipath.json not found. Please run `uipath init` in the project directory."
        )
        return
    config = check_config(root)
    click.echo(
        f"Packaging project {config['project_name']}:{version or config['version']} description {config['description']} authored by {config['authors']}"
    )
    pack_fn(
        config["project_name"],
        config["description"],
        config["entryPoints"],
        version or config["version"],
        config["authors"],
        root,
    )


if __name__ == "__main__":
    pack()
