import logging
from pathlib import PurePath

from httpx import Response
from pydantic import TypeAdapter

from uipath._cli._evals._models._evaluation_set import LLMMockingStrategy
from uipath._cli._push.sw_file_handler import SwFileHandler
from uipath._cli._utils._studio_project import (
    ProjectFile,
    ProjectFolder,
    StudioClient,
    StudioSolutionsClient,
    resolve_path,
)
from uipath.agent.models.agent import (
    AgentDefinition,
    UnknownAgentDefinition,
)

logger = logging.getLogger(__name__)


async def get_file(
    folder: ProjectFolder, path: PurePath, studio_client: StudioClient
) -> Response:
    resolved = resolve_path(folder, path)
    assert isinstance(resolved, ProjectFile), "Path file not found."
    return await studio_client.download_file_async(resolved.id)


async def create_agent_project(solution_id: str, project_name: str) -> str:
    studio_client = StudioSolutionsClient(solution_id=solution_id)
    project = await studio_client.create_project_async(project_name=project_name)
    return project["id"]


async def upload_project_files(project_id: str, root: str) -> None:
    sw_file_handler = SwFileHandler(
        project_id=project_id,
        directory=root,
    )
    await sw_file_handler.upload_source_files({})


async def load_agent_definition(project_id: str) -> AgentDefinition:
    studio_client = StudioClient(project_id=project_id)
    project_structure = await studio_client.get_project_structure_async()

    agent = (
        await get_file(project_structure, PurePath("agent.json"), studio_client)
    ).json()

    evaluators = []
    try:
        evaluators_path = resolve_path(
            project_structure, PurePath("evals", "evaluators")
        )
        if isinstance(evaluators_path, ProjectFolder):
            for file in evaluators_path.files:
                evaluators.append(
                    (
                        await get_file(
                            evaluators_path, PurePath(file.name), studio_client
                        )
                    ).json()
                )
        else:
            logger.warning(
                "Unable to read evaluators from project. Defaulting to empty evaluators."
            )
    except Exception:
        logger.warning(
            "Unable to read evaluators from project. Defaulting to empty evaluators."
        )

    evaluation_sets = []
    try:
        evaluation_sets_path = resolve_path(
            project_structure, PurePath("evals", "eval-sets")
        )
        if isinstance(evaluation_sets_path, ProjectFolder):
            for file in evaluation_sets_path.files:
                evaluation_sets.append(
                    (
                        await get_file(
                            evaluation_sets_path, PurePath(file.name), studio_client
                        )
                    ).json()
                )
        else:
            logger.warning(
                "Unable to read eval-sets from project. Defaulting to empty eval-sets."
            )
    except Exception:
        logger.warning(
            "Unable to read eval-sets from project. Defaulting to empty eval-sets."
        )

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
        "evaluators": evaluators,
        "evaluationSets": evaluation_sets,
        **agent,
    }
    agent_definition = TypeAdapter(AgentDefinition).validate_python(agent_definition)
    if agent_definition and isinstance(agent_definition, UnknownAgentDefinition):
        if agent_definition.evaluation_sets:
            for evaluation_set in agent_definition.evaluation_sets:
                for evaluation in evaluation_set.evaluations:
                    if not evaluation.mocking_strategy:
                        # Migrate lowCode evaluation definitions
                        if evaluation.model_extra.get("simulateTools", False):
                            tools_to_simulate = evaluation.model_extra.get(
                                "toolsToSimulate", []
                            )
                            prompt = evaluation.model_extra.get(
                                "simulationInstructions", ""
                            )
                            evaluation.mocking_strategy = LLMMockingStrategy(
                                prompt=prompt, tools_to_simulate=tools_to_simulate
                            )
    return agent_definition
