import os
from typing import Optional
from urllib.parse import urlparse

import click

from ..spinner import Spinner


def environment_options(function):
    function = click.option(
        "--alpha",
        "domain",
        flag_value="alpha",
        help="Use alpha environment",
    )(function)
    function = click.option(
        "--staging",
        "domain",
        flag_value="staging",
        help="Use staging environment",
    )(function)
    function = click.option(
        "--cloud",
        "domain",
        flag_value="cloud",
        default=True,
        help="Use production environment",
    )(function)
    return function


def get_env_vars(spinner: Optional[Spinner] = None) -> list[str]:
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

    # at this step we know for sure that both base_url and token exist. type checking can be disabled
    return [base_url, token]  # type: ignore


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
