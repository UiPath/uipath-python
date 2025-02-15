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


from .input_args import generate_args

schema = "https://cloud.uipath.com/draft/2024-12/entry-point"
mainFileEntrypoint = "content/main.py"


def validate_config_structure(config_data):
    required_fields = ["type"]
    for field in required_fields:
        if field not in config_data:
            raise Exception(f"config.json is missing the required field: {field}")


def check_config(directory):
    config_path = os.path.join(directory, ".uipath/config.json")
    toml_path = os.path.join(directory, "pyproject.toml")

    if not os.path.isfile(config_path) and not os.path.isfile(toml_path):
        raise Exception("config.json and pyproject.toml not found")

    with open(config_path, "r") as config_file:
        config_data = json.load(config_file)

    validate_config_structure(config_data)

    toml_data = read_toml_project(toml_path)

    return {
        "project_name": toml_data["name"],
        "description": toml_data["description"],
        "type": config_data["type"],
        "version": toml_data["version"],
        "authors": toml_data["authors"],
    }


def generate_operate_file(type):
    project_id = str(uuid.uuid4())

    operate_json_data = {
        "$schema": schema,
        "projectId": project_id,
        "main": mainFileEntrypoint,
        "contentType": type,
        "targetFramework": "Portable",
        "targetRuntime": "python",
        "runtimeOptions": {"requiresUserInteraction": False, "isAttended": False},
    }

    return operate_json_data


def generate_entrypoints_file(input_args, output_args):
    unique_id = str(uuid.uuid4())
    entrypoint_json_data = {
        "$schema": schema,
        "$id": "entry-points.json",
        "entryPoints": [
            {
                "filePath": mainFileEntrypoint,
                "uniqueId": unique_id,
                "type": "agent",
                "input": input_args.get("state", {}),
                "output": output_args.get("state", {}),
            }
        ],
    }

    return entrypoint_json_data


def generate_bindings_content():
    bindings_content = {"version": "2.0", "resources": []}

    return bindings_content


def get_proposed_version(directory):
    output_dir = os.path.join(directory, "_output")
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


def generate_package_desriptor_content():
    package_descriptor_content = {
        "$schema": "https://cloud.uipath.com/draft/2024-12/package-descriptor",
        "files": {
            "operate.json": "content/operate.json",
            "entry-points.json": "content/entry-points.json",
            "bindings.json": "content/bindings_v2.json",
            "main.py": "content/main.py",
        },
    }

    return package_descriptor_content


def get_user_script(directory):
    main_py_path = os.path.join(directory, "main.py")
    if not os.path.isfile(main_py_path):
        raise Exception("main.py file does not exist in the content directory")

    with open(main_py_path, "r") as main_py_file:
        main_py_content = main_py_file.read()

    return main_py_content


def get_user_req_txt(directory):
    requirements_txt_path = os.path.join(directory, "requirements.txt")
    if not os.path.isfile(requirements_txt_path):
        raise Exception("requirements.txt file does not exist in the content directory")

    with open(requirements_txt_path, "r") as requirements_txt_file:
        requirements_txt_content = requirements_txt_file.read()

    return requirements_txt_content


def pack_fn(projectName, description, type, version, authors, directory):
    main_py_content = get_user_script(directory)
    args = generate_args(os.path.join(directory, "main.py"))
    # return
    operate_file = generate_operate_file(type)
    entrypoints_file = generate_entrypoints_file(args["input"], args["output"])
    bindings_content = generate_bindings_content()
    content_types_content = generate_content_types_content()
    [psmdcp_file_name, psmdcp_content] = generate_psmdcp_content(
        projectName, version, description, authors
    )
    nuspec_content = generate_nuspec_content(projectName, version, description, authors)
    rels_content = generate_rels_content(
        f"/{projectName}.nuspec",
        f"/package/services/metadata/core-properties/{psmdcp_file_name}",
    )
    package_descriptor_content = generate_package_desriptor_content()

    requirements_txt_content = get_user_req_txt(directory)
    # Create _output directory if it doesn't exist
    os.makedirs("_output", exist_ok=True)
    with zipfile.ZipFile(
        f"_output/{projectName}.{version}.nupkg", "w", zipfile.ZIP_DEFLATED
    ) as z:
        z.writestr(
            f"./package/services/metadata/core-properties/{psmdcp_file_name}",
            psmdcp_content,
        )
        z.writestr("[Content_Types].xml", content_types_content)

        # z.writestr("content/project.json", "")
        z.writestr(
            "content/package-descriptor.json",
            json.dumps(package_descriptor_content, indent=4),
        )
        z.writestr("content/operate.json", json.dumps(operate_file, indent=4))
        z.writestr("content/entry-points.json", json.dumps(entrypoints_file, indent=4))
        z.writestr("content/bindings_v2.json", json.dumps(bindings_content, indent=4))

        z.writestr(f"{projectName}.nuspec", nuspec_content)
        z.writestr("_rels/.rels", rels_content)
        z.writestr("content/main.py", main_py_content)
        z.writestr("content/requirements.txt", requirements_txt_content)

        if os.path.exists(os.path.join(directory, "pyproject.toml")):
            with open(os.path.join(directory, "pyproject.toml"), "r") as f:
                z.writestr("content/pyproject.toml", f.read())

        if os.path.exists(os.path.join(directory, "README.md")):
            with open(os.path.join(directory, "README.md"), "r") as f:
                z.writestr("content/README.md", f.read())


def read_toml_project(file_path: str) -> dict[str, any]:
    with open(file_path, "rb") as f:
        content = tomllib.load(f)
        return {
            "name": content["project"]["name"],
            "description": content["project"]["description"],
            "version": content["project"]["version"],
            "authors": content["project"].get("authors", [{"name": ""}])[0]["name"],
        }


@click.command()
@click.argument("root", type=str, default="./")
@click.argument("version", type=str, default="")
def pack(root, version):
    proposed_version = get_proposed_version(root)
    if proposed_version and click.confirm(f"Use version {proposed_version}?"):
        version = proposed_version
    # # return
    while not os.path.isfile(os.path.join(root, ".uipath/config.json")):
        root = click.prompt(
            "'.uipath/config.json' not found.\nEnter your project's directory"
        )
    config = check_config(root)
    click.echo(
        f"Packaging project {config['project_name']}:{version or config['version']} description {config['description']} authored by {config['authors']}"
    )
    pack_fn(
        config["project_name"],
        config["description"],
        config["type"],
        version or config["version"],
        config["authors"],
        root,
    )


if __name__ == "__main__":
    pack()
