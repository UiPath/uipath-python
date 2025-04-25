# type: ignore
import logging
import os
from typing import Optional

import click
import requests
from dotenv import load_dotenv

from .spinner import Spinner

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from ._utils._common import get_env_vars
from ._utils._folders import get_personal_workspace_info
from ._utils._processes import get_release_info

logger = logging.getLogger(__name__)
load_dotenv()


def _read_project_name() -> str:
    current_path = os.getcwd()
    toml_path = os.path.join(current_path, "pyproject.toml")
    if not os.path.isfile(toml_path):
        raise Exception("pyproject.toml not found")

    with open(toml_path, "rb") as f:
        content = tomllib.load(f)
        if "project" not in content:
            raise Exception("pyproject.toml is missing the required field: project")
        if "name" not in content["project"]:
            raise Exception(
                "pyproject.toml is missing the required field: project.name"
            )

        return content["project"]["name"]


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("input", required=False, default="{}")
def invoke(entrypoint: Optional[str], input: Optional[str]) -> None:
    """Invoke a remote agent with JSON input."""
    spinner = Spinner("Starting job...")
    spinner.start()

    current_path = os.getcwd()
    load_dotenv(os.path.join(current_path, ".env"), override=True)
    [base_url, token] = get_env_vars(spinner)

    url = f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
    _, personal_workspace_folder_id = get_personal_workspace_info(
        base_url, token, spinner
    )
    project_name = _read_project_name()

    _, release_key = get_release_info(
        base_url, token, project_name, personal_workspace_folder_id, spinner
    )
    payload = {
        "StartInfo": {
            "ReleaseKey": str(release_key),
            "RunAsMe": True,
            "InputArguments": input,
            "EntryPointPath": entrypoint,
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "x-uipath-organizationunitid": str(personal_workspace_folder_id),
    }

    response = requests.post(url, json=payload, headers=headers)
    spinner.stop()

    if response.status_code == 201:
        job_key = None
        try:
            job_key = response.json()["value"][0]["Key"]
        except KeyError:
            click.echo("Error: Failed to get job key from response")
            click.Abort()
        if job_key:
            job_url = f"{base_url}/orchestrator_/jobs(sidepanel:sidepanel/jobs/{job_key}/details)?fid={personal_workspace_folder_id}"
            click.echo("\n✨ Job started successfully!")
            click.echo(
                "\n🔗 Monitor your job here: "
                + click.style(
                    f"\u001b]8;;{job_url}\u001b\\{job_url}\u001b]8;;\u001b\\",
                    fg="bright_blue",
                    bold=True,
                )
                + "\n"
            )
    else:
        click.echo(f"\n❌ Error starting job: {response.text}")
        click.Abort()


if __name__ == "__main__":
    invoke()
