import os
from typing import Optional

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


def get_env_vars(spinner: Optional[Spinner] = None) -> list[str | None]:
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

    return [base_url, token]
