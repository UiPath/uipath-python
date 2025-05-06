# type: ignore
import logging
import os
from typing import Optional

import click
import httpx
from dotenv import load_dotenv

from ._utils._console import ConsoleLogger

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from ._utils._common import get_env_vars
from ._utils._folders import get_personal_workspace_info
from ._utils._processes import get_release_info

logger = logging.getLogger(__name__)
load_dotenv()
console = ConsoleLogger()
client = httpx.Client(follow_redirects=True)


def _read_project_name() -> str:
    current_path = os.getcwd()
    toml_path = os.path.join(current_path, "pyproject.toml")
    if not os.path.isfile(toml_path):
        console.error("pyproject.toml not found.")

    with open(toml_path, "rb") as f:
        content = tomllib.load(f)
        if "project" not in content:
            console.error("pyproject.toml is missing the required field: project.")
        if "name" not in content["project"]:
            console.error("pyproject.toml is missing the required field: project.name.")

        return content["project"]["name"]


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("input", required=False, default="{}")
@click.option(
    "-f",
    "--file",
    required=False,
    type=click.Path(exists=True),
    help="File path for the .json input",
)
def invoke(
    entrypoint: Optional[str], input: Optional[str], file: Optional[str]
) -> None:
    """Invoke an agent published in my workspace."""
    if file:
        _, file_extension = os.path.splitext(file)
        if file_extension != ".json":
            console.error("Input file extension must be '.json'.")
        with open(file) as f:
            input = f.read()
    with console.spinner("Loading configuration ..."):
        current_path = os.getcwd()
        load_dotenv(os.path.join(current_path, ".env"), override=True)
        [base_url, token] = get_env_vars()

        url = f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        _, personal_workspace_folder_id = get_personal_workspace_info(base_url, token)
        project_name = _read_project_name()

        if not personal_workspace_folder_id:
            console.error(
                "No personal workspace found for user. Please try reauthenticating."
            )

        _, release_key = get_release_info(
            base_url, token, project_name, personal_workspace_folder_id
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

        response = client.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        job_key = None
        try:
            job_key = response.json()["value"][0]["Key"]
        except KeyError:
            console.error("Error: Failed to get job key from response")
        if job_key:
            with console.spinner("Starting job ..."):
                job_url = f"{base_url}/orchestrator_/jobs(sidepanel:sidepanel/jobs/{job_key}/details)?fid={personal_workspace_folder_id}"
                console.magic("Job started successfully!")
                console.link("Monitor your job here: ", job_url)
    else:
        console.error(
            f"Error: Failed to start job. Status code: {response.status_code} {response.text}"
        )


if __name__ == "__main__":
    invoke()
