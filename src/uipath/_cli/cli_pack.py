# type: ignore
import json
import logging
import os
import uuid
import zipfile
from string import Template

import click

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .._utils._logs import setup_logging

logger = logging.getLogger(__name__)

schema = "https://cloud.uipath.com/draft/2024-12/entry-point"


def validate_config_structure(config_data):
    required_fields = ["entryPoints"]
    for field in required_fields:
        if field not in config_data:
            logger.error(f"uipath.json is missing the required field: {field}")
            raise Exception(f"uipath.json is missing the required field: {field}")


def check_config(directory):
    config_path = os.path.join(directory, "uipath.json")
    toml_path = os.path.join(directory, "pyproject.toml")

    if not os.path.isfile(config_path):
        logger.error("uipath.json not found, please run `uipath init`")
        raise Exception("uipath.json not found, please run `uipath init`")
    if not os.path.isfile(toml_path):
        logger.error("pyproject.toml not found")
        raise Exception("pyproject.toml not found")

    logger.debug(f"Reading config from: {config_path}")
    with open(config_path, "r") as config_file:
        config_data = json.load(config_file)

    validate_config_structure(config_data)

    logger.debug(f"Reading TOML from: {toml_path}")
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
    logger.debug(f"Generated project ID: {project_id}")

    first_entry = entryPoints[0]
    file_path = first_entry["filePath"]
    type = first_entry["type"]
    logger.debug(f"Using first entry point: {file_path} of type {type}")

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
    logger.debug("Generating entrypoints file")
    entrypoint_json_data = {
        "$schema": schema,
        "$id": "entry-points.json",
        "entryPoints": entryPoints,
    }

    return entrypoint_json_data


def generate_bindings_content():
    logger.debug("Generating empty bindings content")
    bindings_content = {"version": "2.0", "resources": []}

    return bindings_content


def get_proposed_version(directory):
    output_dir = os.path.join(directory, ".uipath")
    if not os.path.exists(output_dir):
        logger.debug("No .uipath directory found, no version to propose")
        return None

    # Get all .nupkg files
    nupkg_files = [f for f in os.listdir(output_dir) if f.endswith(".nupkg")]
    if not nupkg_files:
        logger.debug("No .nupkg files found, no version to propose")
        return None

    # Sort by modification time to get most recent
    latest_file = max(
        nupkg_files, key=lambda f: os.path.getmtime(os.path.join(output_dir, f))
    )
    logger.debug(f"Found latest package: {latest_file}")

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
        logger.debug(f"Proposing new version: {new_version}")
        return new_version
    except Exception:
        logger.debug("Failed to parse version, returning default 0.0.1")
        return "0.0.1"


def generate_content_types_content():
    templates_path = os.path.join(
        os.path.dirname(__file__), "_templates", "[Content_Types].xml.template"
    )
    logger.debug(f"Reading content types template from: {templates_path}")
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
    logger.debug(f"Reading nuspec template from: {templates_path}")
    with open(templates_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return Template(content).substitute(variables)


def generate_rels_content(nuspecPath, psmdcpPath):
    templates_path = os.path.join(
        os.path.dirname(__file__), "_templates", ".rels.template"
    )
    nuspecId = "R" + str(uuid.uuid4()).replace("-", "")[:16]
    psmdcpId = "R" + str(uuid.uuid4()).replace("-", "")[:16]
    logger.debug(f"Generated IDs - nuspec: {nuspecId}, psmdcp: {psmdcpId}")

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
    logger.debug(f"Generated psmdcp file name: {random_file_name}")

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
    logger.debug("Generating package descriptor content")
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
    logger.info("Starting package generation")
    operate_file = generate_operate_file(entryPoints)
    entrypoints_file = generate_entrypoints_file(entryPoints)

    # Get bindings from uipath.json if available
    config_path = os.path.join(directory, "uipath.json")
    if not os.path.exists(config_path):
        logger.error("uipath.json not found, please run `uipath init`")
        raise Exception("uipath.json not found, please run `uipath init`")

    # Define the allowlist of file extensions to include
    file_extensions_included = [".py", ".mermaid", ".json", ".yaml", ".yml"]
    files_included = []

    logger.debug(f"Reading config from: {config_path}")
    with open(config_path, "r") as f:
        config_data = json.load(f)
        if "bindings" in config_data:
            logger.debug("Using bindings from config")
            bindings_content = config_data["bindings"]
        else:
            logger.debug("Generating empty bindings")
            bindings_content = generate_bindings_content()
        if "settings" in config_data:
            settings = config_data["settings"]
            if "fileExtensionsIncluded" in settings:
                file_extensions_included.extend(settings["fileExtensionsIncluded"])
                logger.debug(
                    f"Added custom file extensions: {settings['fileExtensionsIncluded']}"
                )
            if "filesIncluded" in settings:
                files_included = settings["filesIncluded"]
                logger.debug(f"Added custom files: {files_included}")

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
    logger.debug("Created .uipath directory")

    package_path = f".uipath/{projectName}.{version}.nupkg"
    logger.info(f"Creating package at: {package_path}")

    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Add metadata files
        logger.debug("Adding metadata files to package")
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
        logger.debug("Adding project files to package")
        for root, dirs, files in os.walk(directory):
            # Skip all directories that start with .
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                file_extension = os.path.splitext(file)[1].lower()
                if file_extension in file_extensions_included or file in files_included:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, directory)
                    logger.debug(f"Adding file: {rel_path}")
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
                logger.debug(f"Adding optional file: {file}")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        z.writestr(f"content/{file}", f.read())
                except UnicodeDecodeError:
                    with open(file_path, "r", encoding="latin-1") as f:
                        z.writestr(f"content/{file}", f.read())

    logger.info("Package generation completed successfully")


def read_toml_project(file_path: str) -> dict[str, any]:
    logger.debug(f"Reading TOML project from: {file_path}")
    with open(file_path, "rb") as f:
        content = tomllib.load(f)
        if "project" not in content:
            logger.error("pyproject.toml is missing the required field: project")
            raise Exception("pyproject.toml is missing the required field: project")
        if "name" not in content["project"]:
            logger.error("pyproject.toml is missing the required field: project.name")
            raise Exception(
                "pyproject.toml is missing the required field: project.name"
            )
        if "description" not in content["project"]:
            logger.error(
                "pyproject.toml is missing the required field: project.description"
            )
            raise Exception(
                "pyproject.toml is missing the required field: project.description"
            )
        if "version" not in content["project"]:
            logger.error(
                "pyproject.toml is missing the required field: project.version"
            )
            raise Exception(
                "pyproject.toml is missing the required field: project.version"
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
        logger.warning("No pyproject.toml found. Using default version 0.0.1")
        return "0.0.1"
    toml_data = read_toml_project(toml_path)
    return toml_data["version"]


@click.command()
@click.argument("root", type=str, default="./")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def pack(root, verbose):
    # Setup logging based on verbose flag
    setup_logging(should_debug=verbose)

    logger.debug(f"Starting pack command with root: {root}")
    version = get_project_version(root)

    while not os.path.isfile(os.path.join(root, "uipath.json")):
        logger.error(
            "uipath.json not found. Please run `uipath init` in the project directory."
        )
        return

    config = check_config(root)
    if not config["project_name"] or config["project_name"].strip() == "":
        logger.error("Project name cannot be empty")
        raise Exception("Project name cannot be empty")

    if not config["description"] or config["description"].strip() == "":
        logger.error("Project description cannot be empty")
        raise Exception("Project description cannot be empty")

    if not config["authors"] or config["authors"].strip() == "":
        raise Exception("Project authors cannot be empty")

    invalid_chars = ["&", "<", ">", '"', "'", ";"]
    for char in invalid_chars:
        if char in config["project_name"]:
            logger.error(f"Project name contains invalid character: '{char}'")
            raise Exception(f"Project name contains invalid character: '{char}'")

    for char in invalid_chars:
        if char in config["description"]:
            logger.error(f"Project description contains invalid character: '{char}'")
            raise Exception(f"Project description contains invalid character: '{char}'")

    logger.info(
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
