# type: ignore
import json
import os
import uuid
import zipfile
from string import Template

import click

schema = "https://cloud.uipath.com/draft/2024-12/operate"
mainFileEntrypoint = "content/main.py"


def validate_config_structure(config_data):
    required_fields = ["project_name", "description", "type"]
    for field in required_fields:
        if field not in config_data:
            raise Exception(f"config.json is missing the required field: {field}")


def check_config_file(directory):
    config_path = os.path.join(directory, "config.json")
    if not os.path.isfile(config_path):
        raise Exception("config.json file does not exist in the target directory")

    with open(config_path, "r") as config_file:
        config_data = json.load(config_file)

    validate_config_structure(config_data)

    return config_data


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


def generate_entrypoints_file():
    unique_id = str(uuid.uuid4())
    entrypoint_json_data = {
        "$schema": schema,
        "$id": "entry-points.json",
        "entryPoints": [
            {
                "filePath": mainFileEntrypoint,
                "uniqueId": unique_id,
                "type": "codeagent",
                "input": {},
                "output": {},
            }
        ],
    }

    return entrypoint_json_data


def generate_bindings_content():
    bindings_content = {"version": "2.0", "resources": []}

    return bindings_content


def generate_content_types_content():
    templates_path = os.path.join(
        os.path.dirname(__file__), "templates", "[Content_Types].xml.template"
    )
    with open(templates_path, "r") as file:
        content_types_content = file.read()
    return content_types_content


def generate_nuspec_content(projectName, packageVersion, description):
    authors = "UiPath"
    variables = {
        "packageName": projectName,
        "packageVersion": packageVersion,
        "description": description,
        "authors": authors,
    }
    templates_path = os.path.join(
        os.path.dirname(__file__), "templates", "package.nuspec.template"
    )
    with open(templates_path, "r") as f:
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
    with open(templates_path, "r") as f:
        content = f.read()
    return Template(content).substitute(variables)


def generate_psmdcp_content(projectName, version, description):
    templates_path = os.path.join(
        os.path.dirname(__file__), "templates", ".psmdcp.template"
    )
    creator = "UiPath"

    token = str(uuid.uuid4()).replace("-", "")[:32]
    random_file_name = f"{uuid.uuid4().hex[:16]}.psmdcp"
    variables = {
        "creator": creator,
        "description": description,
        "packageVersion": version,
        "projectName": projectName,
        "publicKeyToken": token,
    }
    with open(templates_path, "r") as f:
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


def pack(projectName, description, type, version, directory):
    operate_file = generate_operate_file(type)
    entrypoints_file = generate_entrypoints_file()
    bindings_content = generate_bindings_content()
    content_types_content = generate_content_types_content()
    [psmdcp_file_name, psmdcp_content] = generate_psmdcp_content(
        projectName, version, description
    )
    nuspec_content = generate_nuspec_content(projectName, version, description)
    rels_content = generate_rels_content(
        f"/{projectName}.nuspec",
        f"/package/services/metadata/core-properties/{psmdcp_file_name}",
    )
    package_descriptor_content = generate_package_desriptor_content()
    main_py_content = get_user_script(directory)
    with zipfile.ZipFile(f"{projectName}:{version}.nupkg", "w") as z:
        z.writestr(
            f"./package/services/metadata/core-properties/{psmdcp_file_name}",
            psmdcp_content,
        )
        z.writestr("[Content_Types].xml", content_types_content)

        z.writestr("./content/project.json", "")
        z.writestr(
            "./content/package-descriptor.json",
            json.dumps(package_descriptor_content, indent=4),
        )
        z.writestr("./content/operate.json", json.dumps(operate_file, indent=4))
        z.writestr(
            "./content/entry-points.json", json.dumps(entrypoints_file, indent=4)
        )
        z.writestr("./content/bindings_v2.json", json.dumps(bindings_content, indent=4))

        z.writestr(f"{projectName}.nuspec", nuspec_content)
        z.writestr("./_rels/.rels", rels_content)
        z.writestr("./content/main.py", main_py_content)


@click.command()
@click.option(
    "--directory",
    prompt="Target Directory",
    default=".",
    help="The directory of your project",
)
@click.option(
    "--version", prompt="Version", default="1.0.0", help="Version of this project"
)
def cli_pack(directory, version):
    config = check_config_file(directory)
    click.echo(
        f"Packaging project {config['project_name']}:{version} description {config['description']} and type {config['type']}"
    )
    pack(
        config["project_name"],
        config["description"],
        config["type"],
        version,
        directory,
    )
