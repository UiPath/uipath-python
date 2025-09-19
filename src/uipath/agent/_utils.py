import logging
from pathlib import PurePath

from httpx import Response
from pydantic import TypeAdapter

from uipath._cli._utils._studio_project import (
    ProjectFile,
    ProjectFolder,
    StudioClient,
    resolve_path,
)
from uipath.agent.models.agent import AgentDefinition

logger = logging.getLogger(__name__)


async def get_file(
    folder: ProjectFolder, path: PurePath, studio_client: StudioClient
) -> Response:
    resolved = resolve_path(folder, path)
    assert isinstance(resolved, ProjectFile), "Path file not found."
    return await studio_client.download_file_async(resolved.id)


async def load_agent_definition(project_id: str):
    studio_client = StudioClient(project_id=project_id)
    project_structure = await studio_client.get_project_structure_async()

    agent = (
        await get_file(project_structure, PurePath("agent.json"), studio_client)
    ).json()

    resolved_path = resolve_path(project_structure, PurePath("resources"))
    if isinstance(resolved_path, ProjectFolder):
        resource_folders = resolved_path.folders
    else:
        logger.warning(
            "Unable to read resource information from project. Defaulting to empty resources."
        )
        resource_folders = []

    resources = []
    for resource in resource_folders:
        resources.append(
            (await get_file(resource, PurePath("resource.json"), studio_client)).json()
        )

    agent_definition = {
        "id": project_id,
        "name": project_structure.name,
        "resources": resources,
        **agent,
    }
    return TypeAdapter(AgentDefinition).validate_python(agent_definition)
