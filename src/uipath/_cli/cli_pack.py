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

from ._utils._console import ConsoleLogger

console = ConsoleLogger()

schema = "https://cloud.uipath.com/draft/2024-12/entry-point"


def validate_config_structure(config_data):
    required_fields = ["entryPoints"]
    for field in required_fields:
        if field not in config_data:
            console.error(f"uipath.json is missing the required field: {field}.")


def check_config(directory):
    config_path = os.path.join(directory, "uipath.json")
    toml_path = os.path.join(directory, "pyproject.toml")

    if not os.path.isfile(config_path):
        console.error("uipath.json not found, please run `uipath init`.")
    if not os.path.isfile(toml_path):
        console.error("pyproject.toml not found.")

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


def is_venv_dir(d):
    return (
        os.path.exists(os.path.join(d, "Scripts", "activate"))
        if os.name == "nt"
        else os.path.exists(os.path.join(d, "bin", "activate"))
    )


def pack_fn(projectName, description, entryPoints, version, authors, directory):
    operate_file = generate_operate_file(entryPoints)
    entrypoints_file = generate_entrypoints_file(entryPoints)

    # Get bindings from uipath.json if available
    config_path = os.path.join(directory, "uipath.json")
    if not os.path.exists(config_path):
        console.error("uipath.json not found, please run `uipath init`.")

    # Define the allowlist of file extensions to include
    file_extensions_included = [".py", ".mermaid", ".json", ".yaml", ".yml"]
    files_included = []
    # Binary files that should be read in binary mode
    binary_extensions = [".exe", ""]

    with open(config_path, "r") as f:
        config_data = json.load(f)
        if "bindings" in config_data:
            bindings_content = config_data["bindings"]
        else:
            bindings_content = generate_bindings_content()
        if "settings" in config_data:
            settings = config_data["settings"]
            if "fileExtensionsIncluded" in settings:
                file_extensions_included.extend(settings["fileExtensionsIncluded"])
            if "filesIncluded" in settings:
                files_included = settings["filesIncluded"]

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
        z.writestr("content/bindings_v2.json", json.dumps(bindings_content, indent=4))
        z.writestr(f"{projectName}.nuspec", nuspec_content)
        z.writestr("_rels/.rels", rels_content)

        # Walk through directory and add all files with extensions in the allowlist
        for root, dirs, files in os.walk(directory):
            # Skip all directories that start with . or are a venv
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and not is_venv_dir(os.path.join(root, d))
            ]

            for file in files:
                file_extension = os.path.splitext(file)[1].lower()
                if file_extension in file_extensions_included or file in files_included:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, directory)
                    if file_extension in binary_extensions:
                        # Read binary files in binary mode
                        with open(file_path, "rb") as f:
                            z.writestr(f"content/{rel_path}", f.read())
                    else:
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
        if "project" not in content:
            console.error("pyproject.toml is missing the required field: project.")
        if "name" not in content["project"]:
            console.error("pyproject.toml is missing the required field: project.name.")
        if "description" not in content["project"]:
            console.error(
                "pyproject.toml is missing the required field: project.description."
            )
        if "version" not in content["project"]:
            console.error(
                "pyproject.toml is missing the required field: project.version."
            )

        return {
            "name": content["project"]["name"],
            "description": content["project"]["description"],
            "version": content["project"]["version"],
            "authors": content["project"].get("authors", [{"name": ""}])[0]["name"],
        }


def get_project_version(directory):
    toml_path = os.path.join(directory, "pyproject.toml")
    if not os.path.exists(toml_path):
        console.warning("pyproject.toml not found. Using default version 0.0.1")
        return "0.0.1"
    toml_data = read_toml_project(toml_path)
    return toml_data["version"]


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
@click.argument("root", type=str, default="./")
def pack(root):
    """Pack the project."""
    version = get_project_version(root)

    while not os.path.isfile(os.path.join(root, "uipath.json")):
        console.error(
            "uipath.json not found. Please run `uipath init` in the project directory."
        )
    config = check_config(root)
    if not config["project_name"] or config["project_name"].strip() == "":
        console.error(
            "Project name cannot be empty. Please specify a name in pyproject.toml."
        )

    if not config["description"] or config["description"].strip() == "":
        console.error(
            "Project description cannot be empty. Please specify a description in pyproject.toml."
        )

    if not config["authors"] or config["authors"].strip() == "":
        console.error(
            'Project authors cannot be empty. Please specify authors in pyproject.toml:\n    authors = [{ name = "John Doe" }]'
        )

    invalid_chars = ["&", "<", ">", '"', "'", ";"]
    for char in invalid_chars:
        if char in config["project_name"]:
            console.error(f"Project name contains invalid character: '{char}'")

    for char in invalid_chars:
        if char in config["description"]:
            console.error(f"Project description contains invalid character: '{char}'")

    with console.spinner("Packaging project ..."):
        try:
            pack_fn(
                config["project_name"],
                config["description"],
                config["entryPoints"],
                version or config["version"],
                config["authors"],
                root,
            )
            display_project_info(config)
            console.success("Project successfully packaged.")

        except Exception as e:
            console.error(
                f"Failed to create package {config['project_name']}.{version or config['version']}: {str(e)}"
            )


if __name__ == "__main__":
    pack()
