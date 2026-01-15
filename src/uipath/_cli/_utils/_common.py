import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import click
from dotenv import load_dotenv

from uipath.platform.common import UiPathConfig

from ..._utils._bindings import ResourceOverwrite, ResourceOverwriteParser
from ..._utils.constants import DOTENV_FILE, ENV_UIPATH_ACCESS_TOKEN
from ..spinner import Spinner
from ._console import ConsoleLogger
from ._studio_project import (
    NonCodedAgentProjectException,
    StudioClient,
    StudioProjectMetadata,
)


def get_claim_from_token(claim_name: str) -> str | None:
    import jwt

    token = os.getenv(ENV_UIPATH_ACCESS_TOKEN)
    if not token:
        raise Exception("JWT token not available")
    decoded_token = jwt.decode(token, options={"verify_signature": False})
    return decoded_token.get(claim_name)


def add_cwd_to_path():
    import sys

    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


def environment_options(function):
    function = click.option(
        "--alpha",
        "environment",
        flag_value="alpha",
        help="Use alpha environment",
    )(function)
    function = click.option(
        "--staging",
        "environment",
        flag_value="staging",
        help="Use staging environment",
    )(function)
    function = click.option(
        "--cloud",
        "environment",
        flag_value="cloud",
        help="Use production environment",
    )(function)
    return function


def get_env_vars(spinner: Spinner | None = None) -> list[str]:
    base_url = os.environ.get("UIPATH_URL")
    token = os.environ.get("UIPATH_ACCESS_TOKEN")

    if not all([base_url, token]):
        if spinner:
            spinner.stop()
        click.echo(
            "❌ Missing required environment variables. Please check your .env file contains:"
        )
        click.echo("UIPATH_URL, UIPATH_ACCESS_TOKEN")
        click.get_current_context().exit(1)

    assert base_url and token
    return [base_url, token]


def serialize_object(obj):
    """Recursively serializes an object and all its nested components."""
    # Handle Pydantic models
    if hasattr(obj, "model_dump"):
        return serialize_object(obj.model_dump(by_alias=True))
    elif hasattr(obj, "dict"):
        return serialize_object(obj.dict())
    elif hasattr(obj, "to_dict"):
        return serialize_object(obj.to_dict())
    # Handle dictionaries
    elif isinstance(obj, dict):
        return {k: serialize_object(v) for k, v in obj.items()}
    # Handle lists
    elif isinstance(obj, list):
        return [serialize_object(item) for item in obj]
    # Handle other iterable objects (convert to dict first)
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        try:
            return serialize_object(dict(obj))
        except (TypeError, ValueError):
            return obj
    # Return primitive types as is
    else:
        return obj


def get_org_scoped_url(base_url: str) -> str:
    """Get organization scoped URL from base URL.

    Args:
        base_url: The base URL to scope

    Returns:
        str: The organization scoped URL
    """
    parsed = urlparse(base_url)
    org_name, *_ = parsed.path.strip("/").split("/")
    org_scoped_url = f"{parsed.scheme}://{parsed.netloc}/{org_name}"
    return org_scoped_url


def clean_directory(directory: str) -> None:
    """Clean up Python files in the specified directory.

    Args:
        directory (str): Path to the directory to clean.

    This function removes all Python files (*.py) from the specified directory.
    It's used to prepare a directory for a quickstart agent/coded MCP server.
    """
    for file_name in os.listdir(directory):
        file_path = os.path.join(directory, file_name)

        if os.path.isfile(file_path) and file_name.endswith(".py"):
            os.remove(file_path)


def load_environment_variables():
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), DOTENV_FILE), override=True)


async def ensure_coded_agent_project(studio_client: StudioClient):
    try:
        await studio_client.ensure_coded_agent_project_async()
    except NonCodedAgentProjectException:
        console = ConsoleLogger()
        console.error(
            "The targeted Studio Web project is not of type coded agent. Please check the UIPATH_PROJECT_ID environment variable."
        )


async def may_override_files(
    studio_client: StudioClient, scope: Literal["remote", "local"]
) -> bool:
    from datetime import datetime

    from packaging import version

    remote_metadata = await studio_client.get_project_metadata_async()
    if not remote_metadata:
        return True

    metadata_file_path = UiPathConfig.studio_metadata_file_path

    local_code_version = None

    if os.path.isfile(metadata_file_path):
        with open(metadata_file_path, "r") as f:
            local_data = json.load(f)
            local_metadata = StudioProjectMetadata.model_validate(local_data)
            local_code_version = local_metadata.code_version
        if version.parse(local_code_version) >= version.parse(
            remote_metadata.code_version
        ):
            return True

    local_version_display = local_code_version if local_code_version else "Not Set"

    try:
        push_date = datetime.fromisoformat(remote_metadata.last_push_date)
        formatted_date = push_date.strftime("%b %d, %Y at %I:%M %p UTC")
    except (ValueError, TypeError):
        formatted_date = remote_metadata.last_push_date

    console = ConsoleLogger()
    console.warning("Your local version is behind the remote version.")
    console.info(f"  Remote version:  {remote_metadata.code_version}")
    console.info(f"  Local version:   {local_version_display}")
    console.info(f"  Last publisher:  {remote_metadata.last_push_author}")
    console.info(f"  Last push date:  {formatted_date}")

    return console.confirm(
        f"Do you want to proceed with overwriting the {scope} files?"
    )


async def read_resource_overwrites_from_file(
    directory_path: str | None = None,
) -> dict[str, ResourceOverwrite]:
    """Read resource overwrites from a JSON file."""
    config_file_name = UiPathConfig.config_file_name
    if directory_path is not None:
        file_path = Path(f"{directory_path}/{config_file_name}")
    else:
        file_path = Path(f"{config_file_name}")

    overwrites_dict = {}

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            resource_overwrites = (
                data.get("runtime", {})
                .get("internalArguments", {})
                .get("resourceOverwrites", {})
            )
            for key, value in resource_overwrites.items():
                overwrites_dict[key] = ResourceOverwriteParser.parse(key, value)

    # Return empty dict if file doesn't exist or invalid json
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass

    return overwrites_dict
